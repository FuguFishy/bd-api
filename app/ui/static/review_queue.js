const state = {
  currentStatus: "new",
  items: [],
  selectedItemId: null,
  organisations: [],
  filteredOrganisations: [],
};

const queueItemsEl = document.getElementById("queueItems");
const detailContentEl = document.getElementById("detailContent");
const itemCountEl = document.getElementById("itemCount");
const messageBoxEl = document.getElementById("messageBox");
const filterButtons = document.querySelectorAll(".filter-btn");

function escapeHtml(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
function normaliseName(value) {
  if (!value) return "";
  return String(value)
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/department of the /g, "")
    .replace(/department /g, "")
    .replace(/queensland /g, "")
    .replace(/gov(ernment)?/g, "government")
    .replace(/[^a-z0-9\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function similarityPercent(a, b) {
  const s1 = normaliseName(a);
  const s2 = normaliseName(b);

  if (!s1 || !s2) return 0;
  if (s1 === s2) return 100;

  const longer = s1.length > s2.length ? s1 : s2;
  const shorter = s1.length > s2.length ? s2 : s1;

  let matches = 0;
  for (const ch of shorter) {
    if (longer.includes(ch)) {
      matches++;
    }
  }

  return Math.round((matches / longer.length) * 100);
}
function findBestOrganisationMatch(scrapedName) {
  if (!scrapedName || !state.organisations.length) {
    return null;
  }

  let best = null;
  let bestScore = 0;

  for (const org of state.organisations) {
    const label = org.label || org.name || "";
    const score = similarityPercent(scrapedName, label);

    if (score > bestScore) {
      bestScore = score;
      best = org;
    }
  }

  // Only treat as high-confidence match if score is reasonably high
  return bestScore >= 90 ? { org: best, score: bestScore } : null;
}

function showMessage(text, type = "info") {
  messageBoxEl.textContent = text;
  messageBoxEl.className = `message ${type}`;
}

function clearMessage() {
  messageBoxEl.textContent = "";
  messageBoxEl.className = "message hidden";
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

async function loadOrganisations() {
  try {
    const response = await fetch("/organisations");
    if (!response.ok) {
      throw new Error(`Failed to load organisations (${response.status})`);
    }

    const data = await response.json();
    state.organisations = Array.isArray(data) ? data : [];
    state.filteredOrganisations = [...state.organisations];
  } catch (error) {
    state.organisations = [];
    state.filteredOrganisations = [];
    showMessage(`Organisation list could not be loaded: ${error.message}`, "error");
  }
}

async function loadQueue(status = "new") {
  clearMessage();
  state.currentStatus = status;
  state.selectedItemId = null;

  queueItemsEl.innerHTML = `<div class="empty-state">Loading review items...</div>`;
  detailContentEl.innerHTML = `<div class="empty-state">Select an item to view details.</div>`;

  try {
    const response = await fetch(`/review-queue?status=${encodeURIComponent(status)}`);
    if (!response.ok) {
      throw new Error(`Failed to load items (${response.status})`);
    }

    const items = await response.json();
    state.items = items;
    itemCountEl.textContent = String(items.length);
    renderQueue(items);

    if (items.length > 0) {
      selectItem(items[0].id);
    } else {
      detailContentEl.innerHTML = `<div class="empty-state">No ${escapeHtml(status)} items found.</div>`;
    }
  } catch (error) {
    queueItemsEl.innerHTML = `<div class="empty-state">Could not load review items.</div>`;
    detailContentEl.innerHTML = `<div class="empty-state">Check the API and try again.</div>`;
    showMessage(error.message, "error");
  }
}

function renderQueue(items) {
  if (!items.length) {
    queueItemsEl.innerHTML = `<div class="empty-state">No items in this filter.</div>`;
    return;
  }

  queueItemsEl.innerHTML = items.map(item => `
    <button class="queue-item ${state.selectedItemId === item.id ? "selected" : ""}" data-id="${item.id}">
      <div class="queue-item-top">
        <strong>${escapeHtml(item.job_title || "Untitled job")}</strong>
        <span class="status-pill">${escapeHtml(item.review_status || "—")}</span>
      </div>
      <div class="queue-item-meta">${escapeHtml(item.scraped_organisation || "Unknown organisation")}</div>
      <div class="queue-item-meta">
        Score: ${escapeHtml(item.best_score ?? "—")} · Created: ${escapeHtml(formatDate(item.created_at))}
      </div>
    </button>
  `).join("");

  document.querySelectorAll(".queue-item").forEach(button => {
    button.addEventListener("click", () => {
      const id = Number(button.dataset.id);
      selectItem(id);
    });
  });
}

async function selectItem(id) {
  state.selectedItemId = id;
  renderQueue(state.items);

  const item = state.items.find(x => x.id === id);
  if (!item) {
    detailContentEl.innerHTML = `<div class="empty-state">Item not found.</div>`;
    return;
  }

  renderDetail(item);
  wireOrganisationSearch(item);
}

function buildOrganisationOptions(list, selectedId = null) {
  const options = ['<option value="" disabled>Select an organisation...</option>'];

  for (const org of list) {
    const selected = Number(selectedId) === Number(org.id) ? "selected" : "";
    const displayName = org.label || org.name || `Organisation ${org.id}`;

     options.push(
      `<option value="${org.id}" ${selected}>${escapeHtml(displayName)}</option>`
    );
  }

  return options.join("");
}

function renderDetail(item) {
  const canResolve = item.review_status === "new" || item.review_status === "watchlist";

  detailContentEl.innerHTML = `
    <div class="detail-card">
      <div class="detail-header">
        <div>
          <h2>${escapeHtml(item.job_title || "Untitled job")}</h2>
          <p>${escapeHtml(item.scraped_organisation || "Unknown organisation")}</p>
        </div>
        <span class="status-pill large">${escapeHtml(item.review_status || "—")}</span>
      </div>

      <div class="detail-grid">
        <div><span class="label">Contact name</span><span>${escapeHtml(item.scraped_contact_name || "—")}</span></div>
        <div><span class="label">Contact email</span><span>${escapeHtml(item.scraped_contact_email || "—")}</span></div>
        <div><span class="label">Contact phone</span><span>${escapeHtml(item.scraped_contact_phone || "—")}</span></div>
        <div><span class="label">Best score</span><span>${escapeHtml(item.best_score ?? "—")}</span></div>
        <div><span class="label">Created</span><span>${escapeHtml(formatDate(item.created_at))}</span></div>
        <div><span class="label">Action</span><span>${escapeHtml(item.review_action || "—")}</span></div>
      </div>

      <div class="detail-block">
        <span class="label">Job URL</span>
        ${item.job_url
          ? `<a href="${escapeHtml(item.job_url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(item.job_url)}</a>`
          : `<span>—</span>`}
      </div>

      <div class="detail-block">
        <label class="label" for="reviewNotes">Review notes</label>
        <textarea id="reviewNotes" rows="4" placeholder="Add a short note about this review item...">${escapeHtml(item.review_notes || "")}</textarea>
      </div>

      <div class="detail-block match-panel">
        <label class="label" for="organisationSearch">Find existing organisation</label>
        <input id="organisationSearch" type="text" placeholder="Type part of the organisation name..." ${canResolve ? "" : "disabled"}>
        <select id="existingOrganisationId" size="10" ${canResolve ? "" : "disabled"}>
          ${buildOrganisationOptions(state.filteredOrganisations, item.linked_organisation_id)}
        </select>
      </div>

      <div class="detail-block">
        <label class="label" for="organisationName">Organisation name</label>
        <input id="organisationName" type="text" value="${escapeHtml(item.scraped_organisation || "")}" ${canResolve ? "" : "disabled"}>
      </div>

      <div class="detail-grid">
        <div>
          <label class="label" for="organisationShortName">Short name</label>
          <input id="organisationShortName" type="text" placeholder="Optional" ${canResolve ? "" : "disabled"}>
        </div>
        <div>
          <label class="label" for="sector">Sector</label>
          <input id="sector" type="text" value="Government" ${canResolve ? "" : "disabled"}>
        </div>
        <div>
          <label class="label" for="tier">Tier</label>
          <input id="tier" type="text" value="Target" ${canResolve ? "" : "disabled"}>
        </div>
        <div>
          <label class="label" for="accountStatus">Account status</label>
          <input id="accountStatus" type="text" value="Prospect" ${canResolve ? "" : "disabled"}>
        </div>
      </div>

      <div class="detail-grid">
        <div>
          <label class="label" for="contactName">Contact name</label>
          <input id="contactName" type="text" value="${escapeHtml(item.scraped_contact_name || "")}" ${canResolve ? "" : "disabled"}>
        </div>
        <div>
          <label class="label" for="contactPositionTitle">Contact position title</label>
          <input id="contactPositionTitle" type="text" placeholder="Optional" ${canResolve ? "" : "disabled"}>
        </div>
        <div>
          <label class="label" for="contactDepartment">Contact department</label>
          <input id="contactDepartment" type="text" placeholder="Optional" ${canResolve ? "" : "disabled"}>
        </div>
      </div>

      <div class="action-row">
        <button class="btn btn-secondary" data-action="ignore" ${canResolve ? "" : "disabled"}>Ignore</button>
        <button class="btn btn-secondary" data-action="watchlist" ${canResolve ? "" : "disabled"}>Watchlist</button>
        <button class="btn btn-secondary" data-action="match_existing_organisation" ${canResolve ? "" : "disabled"}>Match existing organisation</button>
        <button class="btn btn-primary" data-action="create_organisation" ${canResolve ? "" : "disabled"}>Create organisation</button>
        <button class="btn btn-primary" data-action="create_organisation_and_contact" ${canResolve ? "" : "disabled"}>Create organisation + contact</button>
      </div>
    </div>
  `;

  document.querySelectorAll("[data-action]").forEach(button => {
    button.addEventListener("click", async () => {
      await resolveItem(item.id, button.dataset.action);
    });
  });
}

function wireOrganisationSearch(item) {
  const searchInput = document.getElementById("organisationSearch");
  const select = document.getElementById("existingOrganisationId");

  if (!searchInput || !select) return;

  const scrapedName = item.scraped_organisation || "";
  searchInput.value = scrapedName;

  const bestMatch = findBestOrganisationMatch(scrapedName);

  if (bestMatch && bestMatch.org) {
    // Filter list around the scraped name and pre-select the best match
    filterOrganisationOptions(scrapedName, bestMatch.org.id);
  } else {
    // No high-confidence match: show full list with no pre-selection
    filterOrganisationOptions("", null);
  }

  searchInput.addEventListener("input", () => {
    filterOrganisationOptions(searchInput.value, null);
  });
}

function filterOrganisationOptions(searchText, selectedId = null) {
  const select = document.getElementById("existingOrganisationId");
  if (!select) return;

  const term = (searchText || "").trim().toLowerCase();

  let filtered = state.organisations;

  if (term) {
    filtered = state.organisations.filter(org =>
      String(org.label || org.name || "").toLowerCase().includes(term)
    );

    if (filtered.length === 0) {
      filtered = state.organisations;
    }
  }

  state.filteredOrganisations = filtered;
  select.innerHTML = buildOrganisationOptions(filtered, selectedId);
}

async function resolveItem(id, action) {
  clearMessage();

  const reviewNotes = document.getElementById("reviewNotes")?.value || "";
  const organisationName = document.getElementById("organisationName")?.value || "";
  const organisationShortName = document.getElementById("organisationShortName")?.value || "";
  const sector = document.getElementById("sector")?.value || "";
  const tier = document.getElementById("tier")?.value || "";
  const accountStatus = document.getElementById("accountStatus")?.value || "";
  const contactName = document.getElementById("contactName")?.value || "";
  const contactPositionTitle = document.getElementById("contactPositionTitle")?.value || "";
  const contactDepartment = document.getElementById("contactDepartment")?.value || "";
  const existingOrganisationId = document.getElementById("existingOrganisationId")?.value || "";

  const payload = {
    review_id: id,
    action,
    review_notes: reviewNotes,
    resolved_by: "manual",
  };

  if (action === "match_existing_organisation") {
    if (!existingOrganisationId) {
      showMessage("Select an existing organisation first.", "error");
      return;
    }

    payload.organisation_id = Number(existingOrganisationId);
  }

  if (action === "create_organisation" || action === "create_organisation_and_contact") {
    payload.organisation_name = organisationName;
    payload.organisation_short_name = organisationShortName || null;
    payload.sector = sector || null;
    payload.tier = tier || null;
    payload.account_status = accountStatus || null;
  }

  if (action === "create_organisation_and_contact") {
    payload.contact_name = contactName;
    payload.contact_position_title = contactPositionTitle || null;
    payload.contact_department = contactDepartment || null;
  }

  try {
    const response = await fetch(`/review-queue/${id}/resolve`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      let message = `Failed to save action (${response.status})`;

      try {
        const errorData = await response.json();

        if (errorData.detail) {
          if (typeof errorData.detail === "string") {
            message = errorData.detail;
          } else if (Array.isArray(errorData.detail)) {
            message = errorData.detail
              .map(x => {
                const field = Array.isArray(x.loc) ? x.loc.join(".") : "field";
                return `${field}: ${x.msg}`;
              })
              .join("; ");
          }
        }
      } catch (_) {}

      throw new Error(message);
    }

    await response.json();
    showMessage("Review item updated successfully.", "success");
    await loadQueue(state.currentStatus);
  } catch (error) {
    showMessage(error.message, "error");
  }
}

filterButtons.forEach(button => {
  button.addEventListener("click", () => {
    filterButtons.forEach(btn => btn.classList.remove("active"));
    button.classList.add("active");
    loadQueue(button.dataset.status);
  });
});

async function initPage() {
  await loadOrganisations();
  await loadQueue("new");
}

initPage();