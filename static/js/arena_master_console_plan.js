(() => {
  "use strict";

  const copyText = async (source) => {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(source.value);
      return;
    }

    source.focus();
    source.select();
    if (!document.execCommand("copy")) {
      throw new Error("Copy command was rejected");
    }
  };

  document.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-copy-target]");
    if (!button) return;

    const source = document.getElementById(button.dataset.copyTarget);
    if (!source) return;

    const status = source.previousElementSibling;
    const originalLabel = button.textContent;
    try {
      await copyText(source);
      button.textContent = "Copied";
      if (status) status.textContent = "YAML copied to clipboard.";
    } catch (error) {
      if (status) status.textContent = "Copy failed. Select the YAML and copy it manually.";
    } finally {
      window.setTimeout(() => {
        button.textContent = originalLabel;
        if (status) status.textContent = "";
      }, 2400);
    }
  });
})();
