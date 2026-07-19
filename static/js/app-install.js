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

  function isInstalledAppWindow() {
    return window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  }

  function showLaunchScreenBriefly() {
    const launchScreen = document.querySelector('[data-app-launch-screen]');
    if (!launchScreen || !isInstalledAppWindow()) {
      return;
    }
    launchScreen.hidden = false;
    window.setTimeout(function () {
      launchScreen.classList.add('is-closing');
      window.setTimeout(function () {
        launchScreen.hidden = true;
        launchScreen.classList.remove('is-closing');
      }, 280);
    }, 1250);
  }

  showLaunchScreenBriefly();

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
