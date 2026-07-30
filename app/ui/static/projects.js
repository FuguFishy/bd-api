const projectForm = document.getElementById("projectForm");
const projectList = document.getElementById("projectList");
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

async function loadProjects() {
  projectList.innerHTML = `<div class="empty-state">Loading projects...</div>`;

  try {
    const response = await fetch("/projects");
    if (!response.ok) {
      throw new Error(`Failed to load projects (${response.status})`);
    }

    const items = await response.json();

    if (!Array.isArray(items) || items.length === 0) {
      projectList.innerHTML = `<div class="empty-state">No projects found yet.</div>`;
      return;
    }

    projectList.innerHTML = `
      <div class="simple-list">
        ${items.map(item => `
          <div class="list-item">
            <div class="item-title">${escapeHtml(item.label || `Project ${item.id}`)}</div>
            <div class="item-meta">ID: ${escapeHtml(item.id)}</div>
          </div>
        `).join("")}
      </div>
    `;
  } catch (error) {
    projectList.innerHTML = `<div class="empty-state">Could not load projects.</div>`;
    showMessage(error.message, "error");
  }
}

projectForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage();

  const formData = new FormData(projectForm);
  const payload = {
    name: String(formData.get("name") || "").trim(),
    status: String(formData.get("status") || "").trim() || null,
    project_type: String(formData.get("project_type") || "").trim() || null,
    organisation_name: String(formData.get("organisation_name") || "").trim()
  };

  if (!payload.name || !payload.organisation_name) {
    showMessage("Project name and organisation are required.", "error");
    return;
  }

  try {
    const response = await fetch("/projects", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || `Failed to save project (${response.status})`);
    }

    projectForm.reset();
    await loadOrganisations();
    showMessage(`Project saved: ${data.name}`, "success");
    loadProjects();
  } catch (error) {
    showMessage(error.message, "error");
  }
});

refreshBtn.addEventListener("click", () => {
  clearMessage();
  loadProjects();
});

async function init() {
  await loadOrganisations();
  await loadProjects();
}

init();
