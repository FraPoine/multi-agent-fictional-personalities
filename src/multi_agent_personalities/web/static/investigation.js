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
