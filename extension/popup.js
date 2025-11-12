let authenticatedUsername = null;

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

async function authenticate(event) {
  event.preventDefault();

  const form = event.target;
  const messageEl = document.getElementById("auth-message");
  const authBtn = document.getElementById("auth-btn");
  const registrationSection = document.getElementById("registration-section");
  const registerBtn = document.getElementById("register-btn");

  messageEl.textContent = "";
  messageEl.classList.remove("success", "error");
  authBtn.disabled = true;
  authBtn.textContent = "Authenticating...";

  const formData = Object.fromEntries(new FormData(form));
  const username = formData.username;
  const password = formData.password;

  const response = await sendMessage({
    type: "AUTHENTICATE",
    payload: { username, password },
  });

  if (!response || !response.ok || !response.authenticated) {
    messageEl.textContent = response?.error || "Authentication failed. Please check your credentials.";
    messageEl.classList.add("error");
    authBtn.disabled = false;
    authBtn.textContent = "Authenticate";
    authenticatedUsername = null;
    registrationSection.style.display = "none";
    registerBtn.disabled = true;
    return;
  }

  messageEl.textContent = "Authentication successful!";
  messageEl.classList.add("success");
  authenticatedUsername = username;
  registrationSection.style.display = "block";
  registerBtn.disabled = false;
  authBtn.textContent = "Authenticated";
}

async function registerUser(event) {
  event.preventDefault();

  if (!authenticatedUsername) {
    const messageEl = document.getElementById("form-message");
    messageEl.textContent = "Please authenticate first.";
    messageEl.classList.add("error");
    return;
  }

  const form = event.target;
  const messageEl = document.getElementById("form-message");
  const registerBtn = document.getElementById("register-btn");

  messageEl.textContent = "";
  messageEl.classList.remove("success", "error");
  registerBtn.disabled = true;
  registerBtn.textContent = "Registering...";

  const formData = Object.fromEntries(new FormData(form));
  formData.username = authenticatedUsername;

  const response = await sendMessage({
    type: "REGISTER_USER",
    payload: formData,
  });

  if (!response || !response.ok) {
    messageEl.textContent = response?.error || "Registration failed.";
    messageEl.classList.add("error");
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
  const qrCodeImg = document.getElementById("telegram-qr-code");

  resultCard.classList.remove("hidden");
  resultMessage.textContent = data.message || "Registration completed!";
  telegramLink.href = data.telegram_deep_link;
  
  // Display QR code if available
  if (data.telegram_qr_code) {
    qrCodeImg.src = data.telegram_qr_code;
    qrCodeImg.style.display = "block";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await loadDetection();
  document.getElementById("auth-form").addEventListener("submit", (event) => {
    authenticate(event).catch((error) => {
      const messageEl = document.getElementById("auth-message");
      const authBtn = document.getElementById("auth-btn");
      messageEl.textContent = error.message;
      messageEl.classList.add("error");
      authBtn.disabled = false;
      authBtn.textContent = "Authenticate";
    });
  });
  document.getElementById("registration-form").addEventListener("submit", (event) => {
    registerUser(event).catch((error) => {
      const messageEl = document.getElementById("form-message");
      const registerBtn = document.getElementById("register-btn");
      messageEl.textContent = error.message;
      messageEl.classList.add("error");
      registerBtn.disabled = false;
      registerBtn.textContent = "Start Monitoring";
    });
  });
});
