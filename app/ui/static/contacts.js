const contactForm = document.getElementById("contactForm");
const contactList = document.getElementById("contactList");
const organisationSelect = document.getElementById("organisationName");
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
  messageBox.textContent = text;
  messageBox.className = `message ${type}`;
}

function clearMessage() {
  messageBox.textContent = "";
  messageBox.className = "message hidden";
}

async function loadOrganisations() {
  try {
    const response = await fetch("/organisations");
    if (!response.ok) {
      throw new Error(`Failed to load organisations (${response.status})`);
    }

    const items = await response.json();

    if (!Array.isArray(items) || items.length === 0) {
      organisationSelect.innerHTML = `<option value="">No organisations found</option>`;
      return;
    }

    organisationSelect.innerHTML = `
      <option value="">Select organisation</option>
      ${items.map(item => `<option value="${escapeHtml(item.label)}">${escapeHtml(item.label)}</option>`).join("")}
    `;
  } catch (error) {
    organisationSelect.innerHTML = `<option value="">Could not load organisations</option>`;
    showMessage(error.message, "error");
  }
}

async function loadContacts() {
  contactList.innerHTML = `<div class="empty-state">Loading contacts...</div>`;

  try {
    const response = await fetch("/contacts");
    if (!response.ok) {
      throw new Error(`Failed to load contacts (${response.status})`);
    }

    const items = await response.json();

    if (!Array.isArray(items) || items.length === 0) {
      contactList.innerHTML = `<div class="empty-state">No contacts found yet.</div>`;
      return;
    }

    contactList.innerHTML = `
      <div class="simple-list">
        ${items.map(item => `
          <div class="list-item">
            <div class="item-title">${escapeHtml(item.label || `Contact ${item.id}`)}</div>
            <div class="item-meta">ID: ${escapeHtml(item.id)}</div>
          </div>
        `).join("")}
      </div>
    `;
  } catch (error) {
    contactList.innerHTML = `<div class="empty-state">Could not load contacts.</div>`;
    showMessage(error.message, "error");
  }
}

contactForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage();

  const formData = new FormData(contactForm);
  const payload = {
    first_name: String(formData.get("first_name") || "").trim(),
    last_name: String(formData.get("last_name") || "").trim(),
    email: String(formData.get("email") || "").trim() || null,
    organisation_name: String(formData.get("organisation_name") || "").trim()
  };

  if (!payload.first_name || !payload.last_name || !payload.organisation_name) {
    showMessage("First name, last name, and organisation are required.", "error");
    return;
  }

  try {
    const response = await fetch("/contacts", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `Failed to save contact (${response.status})`);
    }

    contactForm.reset();
    await loadOrganisations();
    showMessage(`Contact saved: ${data.first_name} ${data.last_name}`, "success");
    loadContacts();
  } catch (error) {
    showMessage(error.message, "error");
  }
});

refreshBtn.addEventListener("click", () => {
  clearMessage();
  loadContacts();
});

async function init() {
  await loadOrganisations();
  await loadContacts();
}

init();
