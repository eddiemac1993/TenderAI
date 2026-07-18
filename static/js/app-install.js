(function () {
  let deferredInstallPrompt = null;

  function getInstallButton() {
    return document.querySelector('[data-install-app-button]');
  }

  function showInstallButton() {
    const button = getInstallButton();
    if (button) {
      button.hidden = false;
    }
  }

  function hideInstallButton() {
    const button = getInstallButton();
    if (button) {
      button.hidden = true;
    }
  }

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/serviceworker.js').catch(function () {
        // TenderAI still works normally when service workers are unavailable.
      });
    });
  }

  window.addEventListener('beforeinstallprompt', function (event) {
    event.preventDefault();
    deferredInstallPrompt = event;
    showInstallButton();
  });

  window.addEventListener('appinstalled', function () {
    deferredInstallPrompt = null;
    hideInstallButton();
  });

  document.addEventListener('click', async function (event) {
    const button = event.target.closest('[data-install-app-button]');
    if (!button || !deferredInstallPrompt) {
      return;
    }
    button.disabled = true;
    deferredInstallPrompt.prompt();
    await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    hideInstallButton();
    button.disabled = false;
  });
})();
