"use strict";

const mutationForms = document.querySelectorAll(".investigation-mutation-form");

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
});

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

function closeResourceDrawer() {
    if (!(resourceDrawer instanceof HTMLElement)) return;
    resourceDrawer.classList.remove("is-open");
    resourceDrawer.setAttribute("aria-hidden", "true");
    if (resourceBackdrop instanceof HTMLElement) resourceBackdrop.hidden = true;
}

if (resourceDrawer instanceof HTMLElement) {
    for (const trigger of document.querySelectorAll("[data-resource-open]")) {
        trigger.addEventListener("click", () => {
            const resource = trigger.dataset.resourceOpen;
            for (const panel of resourceDrawer.querySelectorAll("[data-resource-panel]")) {
                panel.hidden = panel.dataset.resourcePanel !== resource;
            }
            const title = resourceDrawer.querySelector("#resource-drawer-title");
            if (title) title.textContent = trigger.textContent.trim().split("Not available")[0].trim();
            resourceDrawer.classList.add("is-open");
            resourceDrawer.setAttribute("aria-hidden", "false");
            if (resourceBackdrop instanceof HTMLElement) resourceBackdrop.hidden = false;
        });
    }
    for (const trigger of document.querySelectorAll("[data-resource-close]")) {
        trigger.addEventListener("click", closeResourceDrawer);
    }
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") closeResourceDrawer();
    });
}

for (const trigger of document.querySelectorAll("[data-leads-toggle]")) {
    trigger.addEventListener("click", () => {
        document.body.classList.toggle("show-mobile-leads");
    });
}
