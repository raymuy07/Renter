function sendMessage(message) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(message, (response) => {
      resolve(response);
    });
  });
}

async function loadDetection() {
  const response = await sendMessage({ type: "GET_DETECTION" });
  const detectionStatus = document.getElementById("detection-status");
  const detectionDetails = document.getElementById("detection-details");
  const urlEl = document.getElementById("detected-url");
  const paramsEl = document.getElementById("detected-params");

  if (!response || !response.detection) {
    detectionStatus.textContent = "Open a Yad2 search page to begin.";
    detectionDetails.classList.add("hidden");
    return null;
  }

  detectionStatus.textContent = "Yad2 search detected.";
  detectionDetails.classList.remove("hidden");
  urlEl.textContent = response.detection.url;
  paramsEl.textContent = JSON.stringify(response.detection.params, null, 2);

  return response.detection;
}

async function registerUser(event) {
  event.preventDefault();

  const form = event.target;
  const messageEl = document.getElementById("form-message");
  const registerBtn = document.getElementById("register-btn");

  messageEl.textContent = "";
  messageEl.classList.remove("success");
  registerBtn.disabled = true;
  registerBtn.textContent = "Registering...";

  const formData = Object.fromEntries(new FormData(form));

  const response = await sendMessage({
    type: "REGISTER_USER",
    payload: formData,
  });

  if (!response || !response.ok) {
    messageEl.textContent = response?.error || "Registration failed.";
    registerBtn.disabled = false;
    registerBtn.textContent = "Start Monitoring";
    return;
  }

  messageEl.textContent = "Registration successful!";
  messageEl.classList.add("success");

  showResult(response.data);

  registerBtn.textContent = "Registered";
}

function showResult(data) {
  const resultCard = document.getElementById("result-card");
  const resultMessage = document.getElementById("result-message");
  const telegramLink = document.getElementById("telegram-link");

  resultCard.classList.remove("hidden");
  resultMessage.textContent = "Click the link below to finish the Telegram subscription.";
  telegramLink.href = data.telegram_deep_link;
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadDetection();
  document.getElementById("registration-form").addEventListener("submit", (event) => {
    registerUser(event).catch((error) => {
      const messageEl = document.getElementById("form-message");
      const registerBtn = document.getElementById("register-btn");
      messageEl.textContent = error.message;
      registerBtn.disabled = false;
      registerBtn.textContent = "Start Monitoring";
    });
  });
});
