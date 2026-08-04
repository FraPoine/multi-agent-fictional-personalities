"use strict";

function initializeConversationLoading() {
    const form = document.querySelector("[data-conversation-form]");
    const submitButton = document.querySelector("[data-submit-button]");
    const submitLabel = document.querySelector("[data-submit-label]");
    const transcriptPanel = document.querySelector("[data-transcript-panel]");
    const transcriptStatus = document.querySelector("[data-transcript-status]");
    const transcriptBody = document.querySelector("[data-transcript-body]");

    if (
        !form ||
        !submitButton ||
        !submitLabel ||
        !transcriptPanel ||
        !transcriptStatus ||
        !transcriptBody
    ) {
        return;
    }

    const defaultButtonLabel = submitLabel.textContent.trim();
    const serverStatusLabel = transcriptStatus.textContent.trim();
    const serverStatusClass = transcriptStatus.className;
    const serverTranscriptNodes = Array.from(transcriptBody.childNodes);

    form.addEventListener("submit", () => {
        if (form.dataset.submitting === "true") {
            return;
        }

        form.dataset.submitting = "true";
        form.setAttribute("aria-busy", "true");
        transcriptPanel.setAttribute("aria-busy", "true");

        submitButton.disabled = true;
        submitButton.classList.add("primary-action--loading");
        submitLabel.textContent = "Generating conversation…";

        transcriptStatus.classList.remove(
            "status-label--completed",
            "status-label--failed"
        );
        transcriptStatus.classList.add("status-label--running");
        transcriptStatus.textContent = "Running";

        const loadingState = document.createElement("div");
        loadingState.className = "transcript-loading";
        loadingState.setAttribute("role", "status");
        loadingState.setAttribute("aria-live", "polite");

        const spinner = document.createElement("span");
        spinner.className = "loading-spinner";
        spinner.setAttribute("aria-hidden", "true");

        const heading = document.createElement("h3");
        heading.textContent = "Generating conversation";

        const description = document.createElement("p");
        description.textContent = (
            "Sherlock Holmes and Hercule Poirot are investigating " +
            "the case locally."
        );

        loadingState.append(spinner, heading, description);
        transcriptBody.replaceChildren(loadingState);
    });

    window.addEventListener("pageshow", (event) => {
        if (!event.persisted) {
            return;
        }

        delete form.dataset.submitting;
        form.removeAttribute("aria-busy");
        transcriptPanel.removeAttribute("aria-busy");
        submitButton.disabled = false;
        submitButton.classList.remove("primary-action--loading");
        submitLabel.textContent = defaultButtonLabel;
        transcriptStatus.className = serverStatusClass;
        transcriptStatus.textContent = serverStatusLabel;
        transcriptBody.replaceChildren(...serverTranscriptNodes);
    });
}

initializeConversationLoading();
