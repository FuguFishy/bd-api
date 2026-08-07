const contactForm = document.getElementById("contactForm");
const messageBox = document.getElementById("messageBox");
const organisationSelect = document.getElementById("contactOrganisationId");
const organisationNameInput = document.getElementById("contactOrganisationName");

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

if (contactForm) {
  contactForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearMessage();

    const formData = new FormData(contactForm);

    const organisationIdRaw = formData.get("organisation_id");
    const organisationId = organisationIdRaw ? Number(organisationIdRaw) : null;

    const payload = {
      first_name: String(formData.get("first_name") || "").trim(),
      last_name: String(formData.get("last_name") || "").trim(),
      email: normaliseOptionalString(formData.get("email")),
      organisation_id: organisationId,
      organisation_name: normaliseOptionalString(formData.get("organisation_name"))
    };

    if (!payload.first_name || !payload.last_name) {
      showMessage("First name and last name are required.", "error");
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

      showMessage("Contact saved successfully.", "success");
      window.location.reload();
    } catch (error) {
      showMessage(error.message, "error");
    }
  });
}