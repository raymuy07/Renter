const DEFAULT_API_BASE = "http://localhost:8000/api/v1";

function sendMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => resolve(response));
  });
}

async function loadSettings() {
  const response = await sendMessage({ type: "GET_SETTINGS" });
  document.getElementById("apiBaseUrl").value = response?.apiBaseUrl || DEFAULT_API_BASE;
}

async function saveSettings(event) {
  event.preventDefault();
  const messageEl = document.getElementById("save-message");
  const apiBaseUrl = document.getElementById("apiBaseUrl").value || DEFAULT_API_BASE;

  const result = await sendMessage({
    type: "SET_SETTINGS",
    payload: { apiBaseUrl },
  });

  if (result && result.ok) {
    messageEl.textContent = "Saved.";
    messageEl.classList.add("success");
  } else {
    messageEl.textContent = "Unable to save settings.";
    messageEl.classList.remove("success");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadSettings();
  document.getElementById("settings-form").addEventListener("submit", saveSettings);
});
