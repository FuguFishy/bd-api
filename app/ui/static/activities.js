const activityForm = document.getElementById("activityForm");
const activityList = document.getElementById("activityList");
const contactSelect = document.getElementById("contactName");
const organisationSelect = document.getElementById("organisationName");
const projectSelect = document.getElementById("projectName");
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

function formatDateTime(value) {
  if (!value) return "";
  const date = new Date(value);
  if (isNaN(date)) return escapeHtml(value);
  return date.toLocaleString();
}

function setDropdownOptions(element, items, placeholder) {
  if (!Array.isArray(items) || items.length === 0) {
    element.innerHTML = `<option value="">None available</option>`;
    return;
  }

  element.innerHTML = `
    <option value="">${placeholder}</option>
    ${items.map(item => `<option value="${escapeHtml(item.label)}">${escapeHtml(item.label)}</option>`).join("")}
  `;
}

async function loadDropdowns() {
  try {
    const [contactsRes, orgsRes, projectsRes] = await Promise.all([
      fetch("/contacts"),
      fetch("/organisations"),
      fetch("/projects")
    ]);

    if (!contactsRes.ok) throw new Error(`Failed to load contacts (${contactsRes.status})`);
    if (!orgsRes.ok) throw new Error(`Failed to load organisations (${orgsRes.status})`);
    if (!projectsRes.ok) throw new Error(`Failed to load projects (${projectsRes.status})`);

    const contacts = await contactsRes.json();
    const organisations = await orgsRes.json();
    const projects = await projectsRes.json();

    setDropdownOptions(contactSelect, contacts, "Select contact (optional)");
    setDropdownOptions(organisationSelect, organisations, "Select organisation (optional)");
    setDropdownOptions(projectSelect, projects, "Select project (optional)");
  } catch (error) {
    showMessage(error.message, "error");
    contactSelect.innerHTML = `<option value="">Could not load contacts</option>`;
    organisationSelect.innerHTML = `<option value="">Could not load organisations</option>`;
    projectSelect.innerHTML = `<option value="">Could not load projects</option>`;
  }
}

async function loadActivities() {
  activityList.innerHTML = `<div class="empty-state">Loading activities...</div>`;

  try {
    const response = await fetch("/activities");
    if (!response.ok) {
      throw new Error(`Failed to load activities (${response.status})`);
    }

    const items = await response.json();

    if (!Array.isArray(items) || items.length === 0) {
      activityList.innerHTML = `<div class="empty-state">No activities found yet.</div>`;
      return;
    }

    activityList.innerHTML = `
      <div class="simple-list">
        ${items.map(item => `
          <div class="list-item">
            <div class="item-title">${escapeHtml(item.activity_type)} - ${escapeHtml(formatDateTime(item.activity_date))}</div>
            <div class="item-meta">
              ${item.contact_name ? `Contact: ${escapeHtml(item.contact_name)}<br>` : ""}
              ${item.organisation_name ? `Organisation: ${escapeHtml(item.organisation_name)}<br>` : ""}
              ${item.project_name ? `Project: ${escapeHtml(item.project_name)}<br>` : ""}
              ${item.outcome ? `Outcome: ${escapeHtml(item.outcome)}<br>` : ""}
              ${item.notes ? `Notes: ${escapeHtml(item.notes)}` : ""}
            </div>
          </div>
        `).join("")}
      </div>
    `;
  } catch (error) {
    activityList.innerHTML = `<div class="empty-state">Could not load activities.</div>`;
    showMessage(error.message, "error");
  }
}

activityForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage();

  const formData = new FormData(activityForm);
  const activityDateRaw = String(formData.get("activity_date") || "").trim();

  const payload = {
    activity_type: String(formData.get("activity_type") || "").trim(),
    activity_date: activityDateRaw ? new Date(activityDateRaw).toISOString() : "",
    contact_name: String(formData.get("contact_name") || "").trim() || null,
    organisation_name: String(formData.get("organisation_name") || "").trim() || null,
    project_name: String(formData.get("project_name") || "").trim() || null,
    outcome: String(formData.get("outcome") || "").trim() || null,
    notes: String(formData.get("notes") || "").trim() || null
  };

  if (!payload.activity_type || !payload.activity_date) {
    showMessage("Activity type and activity date are required.", "error");
    return;
  }

  try {
    const response = await fetch("/activities", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `Failed to save activity (${response.status})`);
    }

    activityForm.reset();

    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    document.getElementById("activityDate").value = now.toISOString().slice(0, 16);

    showMessage(`Activity saved: ${data.activity_type}`, "success");
    loadActivities();
  } catch (error) {
    showMessage(error.message, "error");
  }
});

refreshBtn.addEventListener("click", () => {
  clearMessage();
  loadActivities();
});

async function init() {
  await loadDropdowns();

  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  document.getElementById("activityDate").value = now.toISOString().slice(0, 16);

  await loadActivities();
}

init();
