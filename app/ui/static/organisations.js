const organisationForm = document.getElementById("organisationForm");
const organisationList = document.getElementById("organisationList");
const messageBox = document.getElementById("messageBox");
const refreshBtn = document.getElementById("refreshBtn");

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showMessage(text, type = "success") {
  if (!messageBox) return;
  messageBox.textContent = text;
  messageBox.className = `message ${type}`;
}

function clearMessage() {
  if (!messageBox) return;
  messageBox.textContent = "";
  messageBox.className = "message hidden";
}

function organisationLink(item) {
  return `/ui/organisations/${encodeURIComponent(item.id)}`;
}

async function loadOrganisations() {
  if (!organisationList) return;

  organisationList.innerHTML = `<div class="empty-state">Loading organisations...</div>`;

  try {
    const response = await fetch("/organisations");
    if (!response.ok) {
      throw new Error(`Failed to load organisations (${response.status})`);
    }

    const items = await response.json();

    if (!Array.isArray(items) || items.length === 0) {
      organisationList.innerHTML = `<div class="empty-state">No organisations found yet.</div>`;
      return;
    }

    organisationList.innerHTML = `
      <div class="simple-list">
        ${items.map(item => `
          <a class="list-item list-item-link" href="${organisationLink(item)}">
            <div class="item-title">${escapeHtml(item.label || `Organisation ${item.id}`)}</div>
            <div class="item-meta">ID: ${escapeHtml(item.id)}</div>
          </a>
        `).join("")}
      </div>
    `;
  } catch (error) {
    organisationList.innerHTML = `<div class="empty-state">Could not load organisations.</div>`;
    showMessage(error.message, "error");
  }
}

if (organisationForm) {
  organisationForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage();

    const formData = new FormData(organisationForm);
    const name = String(formData.get("name") || "").trim();

    if (!name) {
      showMessage("Organisation name is required.", "error");
      return;
    }

    try {
      const response = await fetch("/organisations", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ name })
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || `Failed to save organisation (${response.status})`);
      }

      organisationForm.reset();
      showMessage(`Organisation saved: ${data.name}`, "success");
      loadOrganisations();
    } catch (error) {
      showMessage(error.message, "error");
    }
  });
}

if (refreshBtn) {
  refreshBtn.addEventListener("click", () => {
    clearMessage();
    loadOrganisations();
  });
}

loadOrganisations();