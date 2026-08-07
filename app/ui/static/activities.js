const activityForm = document.getElementById("activityForm");
const messageBox = document.getElementById("messageBox");
const organisationSelect = document.getElementById("activityOrganisationId");
const contactSelect = document.getElementById("activityContactId");
const projectSelect = document.getElementById("activityProjectId");
const returnToInput = document.getElementById("returnTo");

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

function normaliseOptionalNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  return Number(value);
}

function normaliseOptionalString(value) {
  const cleaned = String(value || "").trim();
  return cleaned ? cleaned : null;
}

function syncOrganisationFromLinkedField(selectElement) {
  if (!selectElement || !organisationSelect) return;
  const option = selectElement.options[selectElement.selectedIndex];
  if (!option) return;

  const linkedOrganisationId = option.getAttribute("data-organisation-id");
  if (linkedOrganisationId && !organisationSelect.value) {
    organisationSelect.value = linkedOrganisationId;
  }
}

if (contactSelect) {
  contactSelect.addEventListener("change", () => syncOrganisationFromLinkedField(contactSelect));
}

if (projectSelect) {
  projectSelect.addEventListener("change", () => syncOrganisationFromLinkedField(projectSelect));
}

if (activityForm) {
  activityForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage();

    const formData = new FormData(activityForm);

    const payload = {
      organisation_id: normaliseOptionalNumber(formData.get("organisation_id")),
      contact_id: normaliseOptionalNumber(formData.get("contact_id")),
      project_id: normaliseOptionalNumber(formData.get("project_id")),
      activity_type: String(formData.get("activity_type") || "").trim(),
      activity_date: String(formData.get("activity_date") || "").trim(),
      outcome: normaliseOptionalString(formData.get("outcome")),
      notes: normaliseOptionalString(formData.get("notes")),
      logged_by: normaliseOptionalString(formData.get("logged_by"))
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

      const returnTo = returnToInput ? returnToInput.value.trim() : "";
      if (returnTo) {
        window.location.href = returnTo;
        return;
      }

      if (payload.organisation_id) {
        window.location.href = `/ui/organisations/${payload.organisation_id}`;
        return;
      }

      showMessage("Activity saved successfully.", "success");
      window.location.reload();
    } catch (error) {
      showMessage(error.message, "error");
    }
  });
}