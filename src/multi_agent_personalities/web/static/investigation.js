"use strict";

const mutationForms = document.querySelectorAll(".investigation-mutation-form");
const lobbyForm = document.querySelector("[data-investigation-lobby-form]");

function lobbySelectionIsValid() {
    if (!(lobbyForm instanceof HTMLFormElement)) return true;
    const minimum = Number(lobbyForm.dataset.minInvestigators);
    const required = Number(lobbyForm.dataset.requiredInvestigatorCount);
    const selected = lobbyForm.querySelectorAll(
        'input[name="characters"]:checked:not(:disabled)'
    ).length;
    const hasCase = lobbyForm.querySelector('input[name="case_id"]:checked') !== null;
    return hasCase && selected >= minimum && selected === required;
}

function updateLobbyStartButton() {
    if (!(lobbyForm instanceof HTMLFormElement)) return;
    const button = lobbyForm.querySelector("[data-investigation-start]");
    const requirement = lobbyForm.querySelector("[data-investigator-requirement]");
    const valid = lobbySelectionIsValid();
    if (button instanceof HTMLButtonElement) {
        button.disabled = !valid;
        button.setAttribute("aria-disabled", String(!valid));
    }
    if (requirement instanceof HTMLElement) {
        requirement.dataset.selectionValid = String(valid);
    }
}

function resetMutationForm(form) {
    form.removeAttribute("aria-busy");
    for (const button of form.querySelectorAll('button[type="submit"]')) {
        button.disabled = false;
        if (button.dataset.originalLabel) {
            button.textContent = button.dataset.originalLabel;
        }
    }
}

for (const form of mutationForms) {
    for (const button of form.querySelectorAll('button[type="submit"]')) {
        button.dataset.originalLabel = button.textContent;
    }

    form.addEventListener("submit", (event) => {
        if (form === lobbyForm && !lobbySelectionIsValid()) {
            event.preventDefault();
            updateLobbyStartButton();
            return;
        }
        if (!form.checkValidity()) {
            return;
        }

        if (form.getAttribute("aria-busy") === "true") {
            event.preventDefault();
            return;
        }

        form.setAttribute("aria-busy", "true");
        const loadingLabel = form.dataset.loadingLabel || "Working…";
        for (const button of form.querySelectorAll('button[type="submit"]')) {
            button.disabled = true;
            button.textContent = loadingLabel;
        }
    });
}

window.addEventListener("pageshow", () => {
    for (const form of mutationForms) {
        resetMutationForm(form);
    }
    updateLobbyStartButton();
});

if (lobbyForm instanceof HTMLFormElement) {
    for (const input of lobbyForm.querySelectorAll(
        'input[name="characters"], input[name="case_id"]'
    )) {
        input.addEventListener("change", updateLobbyStartButton);
    }
    updateLobbyStartButton();
}

const rulesDialog = document.querySelector("[data-rules-dialog]");
if (rulesDialog instanceof HTMLDialogElement) {
    for (const trigger of document.querySelectorAll("[data-rules-open]")) {
        trigger.addEventListener("click", () => rulesDialog.showModal());
    }
    for (const trigger of document.querySelectorAll("[data-rules-close]")) {
        trigger.addEventListener("click", () => rulesDialog.close());
    }
    rulesDialog.addEventListener("click", (event) => {
        if (event.target === rulesDialog) rulesDialog.close();
    });
}

const resourceDrawer = document.querySelector("[data-resource-drawer]");
const resourceBackdrop = document.querySelector(".resource-backdrop");
let resourceReturnFocus = null;

function closeResourceDrawer() {
    if (!(resourceDrawer instanceof HTMLElement)) return;
    resourceDrawer.classList.remove("is-open");
    resourceDrawer.setAttribute("aria-hidden", "true");
    if (resourceBackdrop instanceof HTMLElement) resourceBackdrop.hidden = true;
    if (resourceReturnFocus instanceof HTMLElement) resourceReturnFocus.focus();
}

if (resourceDrawer instanceof HTMLElement) {
    for (const trigger of resourceDrawer.querySelectorAll("[data-map-select]")) {
        trigger.addEventListener("click", () => {
            const selectedMap = trigger.dataset.mapSelect;
            for (const button of resourceDrawer.querySelectorAll("[data-map-select]")) {
                button.setAttribute("aria-pressed", String(button === trigger));
            }
            for (const item of resourceDrawer.querySelectorAll("[data-map-item]")) {
                item.hidden = item.dataset.mapItem !== selectedMap;
            }
        });
    }
    for (const trigger of document.querySelectorAll("[data-resource-open]")) {
        trigger.addEventListener("click", () => {
            const resource = trigger.dataset.resourceOpen;
            resourceReturnFocus = trigger;
            for (const panel of resourceDrawer.querySelectorAll("[data-resource-panel]")) {
                panel.hidden = panel.dataset.resourcePanel !== resource;
            }
            const title = resourceDrawer.querySelector("#resource-drawer-title");
            if (title) title.textContent = trigger.getAttribute("aria-label") || trigger.textContent.trim();
            resourceDrawer.classList.add("is-open");
            resourceDrawer.setAttribute("aria-hidden", "false");
            if (resourceBackdrop instanceof HTMLElement) resourceBackdrop.hidden = false;
            resourceDrawer.focus();
        });
    }
    for (const trigger of document.querySelectorAll("[data-resource-close]")) {
        trigger.addEventListener("click", closeResourceDrawer);
    }
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeResourceDrawer();
    });
}

const leadBackdrop = document.querySelector(".lead-backdrop");

function setLeadPanelOpen(open) {
    document.body.classList.toggle("show-mobile-leads", open);
    for (const trigger of document.querySelectorAll("[data-leads-toggle]")) {
        trigger.setAttribute("aria-expanded", String(open));
    }
    if (leadBackdrop instanceof HTMLElement) leadBackdrop.hidden = !open;
}

for (const trigger of document.querySelectorAll("[data-leads-toggle]")) {
    trigger.addEventListener("click", () => {
        setLeadPanelOpen(!document.body.classList.contains("show-mobile-leads"));
    });
}

for (const trigger of document.querySelectorAll("[data-leads-close]")) {
    trigger.addEventListener("click", () => setLeadPanelOpen(false));
}

document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setLeadPanelOpen(false);
});
