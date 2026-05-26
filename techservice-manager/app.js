const state = {
  clients: [],
  equipment: [],
  requests: [],
  interactions: [],
  requestFilter: "",
};

const statuses = ["Новая", "В работе", "Ожидает клиента", "Закрыта", "Отменена"];

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Ошибка выполнения запроса");
  }
  return data;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function toast(message, isError = false) {
  const element = $("#toast");
  element.textContent = message;
  element.style.background = isError ? "#9a3d32" : "";
  element.classList.add("show");
  setTimeout(() => element.classList.remove("show"), 2600);
}

function emptyRow(colspan, text) {
  return `<tr><td class="empty" colspan="${colspan}">${text}</td></tr>`;
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function badge(status) {
  const cls = status === "Закрыта" ? "done" : status === "В работе" ? "work" : status === "Ожидает клиента" ? "wait" : "";
  return `<span class="badge ${cls}">${escapeHtml(status)}</span>`;
}

function fillSelect(select, items, placeholder, getLabel = (item) => item.name) {
  select.innerHTML = `<option value="">${placeholder}</option>`;
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = getLabel(item);
    select.append(option);
  }
}

function renderStats(summary) {
  $("#statClients").textContent = summary.clients;
  $("#statEquipment").textContent = summary.equipment;
  $("#statRequests").textContent = summary.requests;
  $("#statActive").textContent = summary.active;
  $("#statInteractions").textContent = summary.interactions;
}

function renderClients() {
  const body = $("#clientsTable");
  body.innerHTML = state.clients.length
    ? state.clients
        .map(
          (client) => `
          <tr>
            <td>${client.id}</td>
            <td>${escapeHtml(client.name)}</td>
            <td>${escapeHtml(client.phone)}</td>
            <td>${escapeHtml(client.email || "—")}</td>
            <td>${escapeHtml(client.address || "—")}</td>
          </tr>`
        )
        .join("")
    : emptyRow(5, "Клиенты пока не добавлены.");
}

function renderEquipment() {
  const body = $("#equipmentTable");
  body.innerHTML = state.equipment.length
    ? state.equipment
        .map(
          (item) => `
          <tr>
            <td>${item.id}</td>
            <td>${escapeHtml(item.title)}</td>
            <td>${escapeHtml(item.client_name)}</td>
            <td>${escapeHtml(item.serial_number || "—")}</td>
            <td>${escapeHtml(item.location || "—")}</td>
          </tr>`
        )
        .join("")
    : emptyRow(5, "Оборудование пока не добавлено.");
}

function renderRequests() {
  const body = $("#requestsTable");
  body.innerHTML = state.requests.length
    ? state.requests
        .map(
          (request) => `
          <tr>
            <td>${request.id}</td>
            <td>
              <strong>${escapeHtml(request.title)}</strong><br />
              <span>${escapeHtml(request.description || "Без описания")}</span>
            </td>
            <td>${escapeHtml(request.client_name)}</td>
            <td>${escapeHtml(request.equipment_title || "—")}</td>
            <td>${badge(request.status)}</td>
            <td>
              <form class="status-control" data-id="${request.id}">
                <select name="status">
                  ${statuses.map((status) => `<option ${status === request.status ? "selected" : ""}>${status}</option>`).join("")}
                </select>
                <button>OK</button>
              </form>
            </td>
          </tr>`
        )
        .join("")
    : emptyRow(6, "Заявки пока не созданы.");

  $("#recentRequests").innerHTML = state.requests.length
    ? state.requests
        .slice(0, 5)
        .map(
          (request) => `
          <tr>
            <td>${request.id}</td>
            <td>${escapeHtml(request.title)}</td>
            <td>${escapeHtml(request.client_name)}</td>
            <td>${escapeHtml(request.priority)}</td>
            <td>${badge(request.status)}</td>
          </tr>`
        )
        .join("")
    : emptyRow(5, "Пока заявок нет. Перейдите в раздел «Заявки», чтобы добавить первую.");
}

function renderInteractions() {
  const body = $("#interactionsTable");
  body.innerHTML = state.interactions.length
    ? state.interactions
        .map(
          (item) => `
          <tr>
            <td>${item.id}</td>
            <td>${escapeHtml(item.client_name)}</td>
            <td>${escapeHtml(item.request_title || "—")}</td>
            <td>${escapeHtml(item.interaction_type)}</td>
            <td>${escapeHtml(item.responsible || "—")}</td>
            <td>${escapeHtml(item.content)}</td>
          </tr>`
        )
        .join("")
    : emptyRow(6, "История взаимодействий пока пуста.");
}

function renderSelects() {
  $$('select[name="client_id"]').forEach((select) => fillSelect(select, state.clients, "Выберите клиента"));
  $$('select[name="equipment_id"]').forEach((select) =>
    fillSelect(select, state.equipment, "Без привязки к оборудованию", (item) => `${item.title} — ${item.client_name}`)
  );
  $$('select[name="request_id"]').forEach((select) =>
    fillSelect(select, state.requests, "Без привязки к заявке", (item) => `#${item.id} ${item.title}`)
  );
}

async function loadAll() {
  const [summary, clients, equipment, requests, interactions] = await Promise.all([
    api("/api/summary"),
    api("/api/clients"),
    api("/api/equipment"),
    api(`/api/requests${state.requestFilter ? `?status=${encodeURIComponent(state.requestFilter)}` : ""}`),
    api("/api/interactions"),
  ]);
  state.clients = clients;
  state.equipment = equipment;
  state.requests = requests;
  state.interactions = interactions;
  renderStats(summary);
  renderClients();
  renderEquipment();
  renderRequests();
  renderInteractions();
  renderSelects();
}

function bindNavigation() {
  $$(".nav__item").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".nav__item").forEach((item) => item.classList.remove("active"));
      $$(".page").forEach((page) => page.classList.remove("active"));
      button.classList.add("active");
      $(`#${button.dataset.page}`).classList.add("active");
    });
  });
}

function bindForms() {
  $("#clientForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/clients", { method: "POST", body: JSON.stringify(formData(event.target)) });
      event.target.reset();
      toast("Клиент сохранён");
      await loadAll();
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("#equipmentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/equipment", { method: "POST", body: JSON.stringify(formData(event.target)) });
      event.target.reset();
      toast("Оборудование сохранено");
      await loadAll();
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("#requestForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/requests", { method: "POST", body: JSON.stringify(formData(event.target)) });
      event.target.reset();
      toast("Заявка создана");
      await loadAll();
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("#interactionForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await api("/api/interactions", { method: "POST", body: JSON.stringify(formData(event.target)) });
      event.target.reset();
      toast("Запись истории сохранена");
      await loadAll();
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("#clientSearch").addEventListener("submit", async (event) => {
    event.preventDefault();
    const search = new FormData(event.target).get("search");
    state.clients = await api(`/api/clients?search=${encodeURIComponent(search)}`);
    renderClients();
  });

  $("#statusFilter").addEventListener("submit", async (event) => {
    event.preventDefault();
    state.requestFilter = new FormData(event.target).get("status");
    await loadAll();
  });

  $("#requestsTable").addEventListener("submit", async (event) => {
    const form = event.target.closest(".status-control");
    if (!form) return;
    event.preventDefault();
    try {
      await api(`/api/requests/${form.dataset.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: form.status.value, responsible: "Диспетчер" }),
      });
      toast("Статус заявки обновлён");
      await loadAll();
    } catch (error) {
      toast(error.message, true);
    }
  });

  $("#seedButton").addEventListener("click", async () => {
    try {
      await api("/api/seed", { method: "POST", body: "{}" });
      toast("Демонстрационная база заполнена");
      await loadAll();
    } catch (error) {
      toast(error.message, true);
    }
  });
}

bindNavigation();
bindForms();
loadAll().catch((error) => toast(error.message, true));
