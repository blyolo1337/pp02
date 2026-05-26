import json
import mimetypes
import sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "techservice.db"
HOST = "127.0.0.1"
PORT = 8000


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                email TEXT,
                address TEXT,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS equipment (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                serial_number TEXT,
                location TEXT,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS service_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                equipment_id INTEGER,
                title TEXT NOT NULL,
                description TEXT,
                priority TEXT NOT NULL,
                status TEXT NOT NULL,
                engineer TEXT,
                deadline TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (equipment_id) REFERENCES equipment(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                request_id INTEGER,
                interaction_type TEXT NOT NULL,
                responsible TEXT,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
                FOREIGN KEY (request_id) REFERENCES service_requests(id) ON DELETE SET NULL
            );
            """
        )


def rows(query, params=()):
    with get_db() as db:
        return [dict(row) for row in db.execute(query, params).fetchall()]


def row(query, params=()):
    with get_db() as db:
        item = db.execute(query, params).fetchone()
        return dict(item) if item else None


def require(payload, *fields):
    missing = [field for field in fields if not str(payload.get(field, "")).strip()]
    if missing:
        raise ValueError("Заполните обязательные поля: " + ", ".join(missing))


def create_client(payload):
    require(payload, "name", "phone")
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO clients (name, phone, email, address, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                payload["name"].strip(),
                payload["phone"].strip(),
                payload.get("email", "").strip(),
                payload.get("address", "").strip(),
                payload.get("note", "").strip(),
            ),
        )
        db.commit()
        item = db.execute("SELECT * FROM clients WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(item)


def create_equipment(payload):
    require(payload, "client_id", "title")
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO equipment (client_id, title, serial_number, location)
            VALUES (?, ?, ?, ?)
            """,
            (
                int(payload["client_id"]),
                payload["title"].strip(),
                payload.get("serial_number", "").strip(),
                payload.get("location", "").strip(),
            ),
        )
        db.commit()
        item = db.execute("SELECT * FROM equipment WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(item)


def create_request(payload):
    require(payload, "client_id", "title", "priority", "status")
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO service_requests
            (client_id, equipment_id, title, description, priority, status, engineer, deadline)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(payload["client_id"]),
                int(payload["equipment_id"]) if payload.get("equipment_id") else None,
                payload["title"].strip(),
                payload.get("description", "").strip(),
                payload["priority"].strip(),
                payload["status"].strip(),
                payload.get("engineer", "").strip(),
                payload.get("deadline", "").strip(),
            ),
        )
        request_id = cursor.lastrowid
        db.execute(
            """
            INSERT INTO interactions (client_id, request_id, interaction_type, responsible, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(payload["client_id"]),
                request_id,
                "Создание заявки",
                payload.get("engineer", "Диспетчер").strip() or "Диспетчер",
                f"Создана заявка: {payload['title'].strip()}",
            ),
        )
        db.commit()
        item = db.execute("SELECT * FROM service_requests WHERE id = ?", (request_id,)).fetchone()
        return dict(item)


def create_interaction(payload):
    require(payload, "client_id", "interaction_type", "content")
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO interactions
            (client_id, request_id, interaction_type, responsible, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(payload["client_id"]),
                int(payload["request_id"]) if payload.get("request_id") else None,
                payload["interaction_type"].strip(),
                payload.get("responsible", "").strip(),
                payload["content"].strip(),
            ),
        )
        db.commit()
        item = db.execute("SELECT * FROM interactions WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return dict(item)


def update_request_status(request_id, payload):
    require(payload, "status")
    with get_db() as db:
        request = db.execute("SELECT * FROM service_requests WHERE id = ?", (request_id,)).fetchone()
        if not request:
            raise ValueError("Заявка не найдена")
        db.execute("UPDATE service_requests SET status = ? WHERE id = ?", (payload["status"], request_id))
        db.execute(
            """
            INSERT INTO interactions (client_id, request_id, interaction_type, responsible, content)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request["client_id"],
                request_id,
                "Смена статуса",
                payload.get("responsible", "Система"),
                f"Статус заявки изменён на «{payload['status']}»",
            ),
        )
        db.commit()
        item = db.execute("SELECT * FROM service_requests WHERE id = ?", (request_id,)).fetchone()
        return dict(item)


def seed_demo_data():
    with get_db() as db:
        db.executescript(
            """
            DELETE FROM interactions;
            DELETE FROM service_requests;
            DELETE FROM equipment;
            DELETE FROM clients;
            """
        )
    client_a = create_client(
        {
            "name": "ООО «Альфа»",
            "phone": "+7 (900) 111-22-33",
            "email": "office@alpha.ru",
            "address": "г. Москва, ул. Сервисная, 12",
            "note": "Постоянный клиент, обслуживание по договору.",
        }
    )
    client_b = create_client(
        {
            "name": "ИП Смирнов А.А.",
            "phone": "+7 (900) 444-55-66",
            "email": "smirnov@example.ru",
            "address": "г. Москва, пр-т Мира, 7",
            "note": "Приоритетные заявки по кассовому оборудованию.",
        }
    )
    equipment_a = create_equipment(
        {
            "client_id": client_a["id"],
            "title": "Сервер Dell PowerEdge",
            "serial_number": "DELL-7788",
            "location": "Серверная",
        }
    )
    create_equipment(
        {
            "client_id": client_b["id"],
            "title": "МФУ HP LaserJet",
            "serial_number": "HP-4455",
            "location": "Офис продаж",
        }
    )
    request = create_request(
        {
            "client_id": client_a["id"],
            "equipment_id": equipment_a["id"],
            "title": "Проверить резервное копирование",
            "description": "Клиент сообщил об ошибке ночного бэкапа.",
            "priority": "Высокий",
            "status": "В работе",
            "engineer": "Иванов И.И.",
            "deadline": "2026-05-30",
        }
    )
    create_interaction(
        {
            "client_id": client_a["id"],
            "request_id": request["id"],
            "interaction_type": "Звонок",
            "responsible": "Диспетчер",
            "content": "Уточнено время удалённого подключения.",
        }
    )


def summary():
    return {
        "clients": row("SELECT COUNT(*) AS total FROM clients")["total"],
        "equipment": row("SELECT COUNT(*) AS total FROM equipment")["total"],
        "requests": row("SELECT COUNT(*) AS total FROM service_requests")["total"],
        "active": row(
            "SELECT COUNT(*) AS total FROM service_requests WHERE status NOT IN ('Закрыта', 'Отменена')"
        )["total"],
        "interactions": row("SELECT COUNT(*) AS total FROM interactions")["total"],
    }


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, message, status=400):
        self.send_json({"error": message}, status)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        try:
            if path == "/api/summary":
                return self.send_json(summary())
            if path == "/api/clients":
                search = query.get("search", [""])[0].strip()
                if search:
                    pattern = f"%{search}%"
                    return self.send_json(
                        rows(
                            """
                            SELECT * FROM clients
                            WHERE name LIKE ? OR phone LIKE ? OR email LIKE ?
                            ORDER BY id DESC
                            """,
                            (pattern, pattern, pattern),
                        )
                    )
                return self.send_json(rows("SELECT * FROM clients ORDER BY id DESC"))
            if path == "/api/equipment":
                return self.send_json(
                    rows(
                        """
                        SELECT equipment.*, clients.name AS client_name
                        FROM equipment
                        JOIN clients ON clients.id = equipment.client_id
                        ORDER BY equipment.id DESC
                        """
                    )
                )
            if path == "/api/requests":
                status = query.get("status", [""])[0]
                params = []
                where = ""
                if status:
                    where = "WHERE service_requests.status = ?"
                    params.append(status)
                return self.send_json(
                    rows(
                        f"""
                        SELECT service_requests.*, clients.name AS client_name, equipment.title AS equipment_title
                        FROM service_requests
                        JOIN clients ON clients.id = service_requests.client_id
                        LEFT JOIN equipment ON equipment.id = service_requests.equipment_id
                        {where}
                        ORDER BY service_requests.id DESC
                        """,
                        params,
                    )
                )
            if path == "/api/interactions":
                return self.send_json(
                    rows(
                        """
                        SELECT interactions.*, clients.name AS client_name, service_requests.title AS request_title
                        FROM interactions
                        JOIN clients ON clients.id = interactions.client_id
                        LEFT JOIN service_requests ON service_requests.id = interactions.request_id
                        ORDER BY interactions.id DESC
                        """
                    )
                )
            return self.send_static(path)
        except Exception as exc:
            return self.send_error_json(str(exc), 500)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            payload = self.read_json()
            if path == "/api/clients":
                return self.send_json(create_client(payload), 201)
            if path == "/api/equipment":
                return self.send_json(create_equipment(payload), 201)
            if path == "/api/requests":
                return self.send_json(create_request(payload), 201)
            if path == "/api/interactions":
                return self.send_json(create_interaction(payload), 201)
            if path == "/api/seed":
                seed_demo_data()
                return self.send_json({"ok": True})
            return self.send_error_json("Маршрут не найден", 404)
        except ValueError as exc:
            return self.send_error_json(str(exc), 400)
        except Exception as exc:
            return self.send_error_json(str(exc), 500)

    def do_PATCH(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        try:
            if len(parts) == 4 and parts[:2] == ["api", "requests"] and parts[3] == "status":
                return self.send_json(update_request_status(int(parts[2]), self.read_json()))
            return self.send_error_json("Маршрут не найден", 404)
        except ValueError as exc:
            return self.send_error_json(str(exc), 400)
        except Exception as exc:
            return self.send_error_json(str(exc), 500)

    def send_static(self, path):
        if path == "/":
            path = "/index.html"
        file_path = (ROOT / path.lstrip("/")).resolve()
        if ROOT not in file_path.parents and file_path != ROOT:
            return self.send_error_json("Недопустимый путь", 403)
        if not file_path.exists() or not file_path.is_file():
            return self.send_error_json("Файл не найден", 404)
        content = file_path.read_bytes()
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, format, *args):
        return


if __name__ == "__main__":
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"TechService Manager запущен: http://{HOST}:{PORT}")
    print("Для остановки нажмите Ctrl+C")
    server.serve_forever()
