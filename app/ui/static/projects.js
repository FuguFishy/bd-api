const projectForm = document.getElementById("projectForm");
const messageBox = document.getElementById("messageBox");
const organisationSelect = document.getElementById("projectOrganisationId");
const organisationNameInput = document.getElementById("projectOrganisationName");

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

function normaliseOptionalString(value) {
  const cleaned = String(value || "").trim();
  return cleaned ? cleaned : null;
}

if (organisationSelect && organisationNameInput) {
  organisationSelect.addEventListener("change", () => {
    if (organisationSelect.value) {
      const selectedOption = organisationSelect.options[organisationSelect.selectedIndex];
      if (selectedOption && selectedOption.text) {
        organisationNameInput.value = selectedOption.text.trim();
      }
    }
  });
}

if (projectForm) {
  projectForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage();

    const formData = new FormData(projectForm);

    const organisationIdRaw = formData.get("organisation_id");
    const organisationId = organisationIdRaw ? Number(organisationIdRaw) : null;

    const selectedOption =
      organisationSelect && organisationSelect.selectedIndex >= 0
        ? organisationSelect.options[organisationSelect.selectedIndex]
        : null;

    const derivedOrganisationName =
      selectedOption && organisationSelect.value
        ? selectedOption.text.trim()
        : null;

    const payload = {
      name: String(formData.get("name") || "").trim(),
      status: normaliseOptionalString(formData.get("status")),
      project_type: normaliseOptionalString(formData.get("project_type")),
      organisation_id: organisationId,
      organisation_name:
        derivedOrganisationName || normaliseOptionalString(formData.get("organisation_name"))
    };

    if (!payload.name) {
      showMessage("Project name is required.", "error");
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

      showMessage("Project saved successfully.", "success");
      window.location.reload();
    } catch (error) {
      showMessage(error.message, "error");
    }
  });
}