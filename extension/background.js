const DEFAULT_API_BASE = "http://localhost:8000/api";

let currentDetection = null;

async function getApiBaseUrl() {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ apiBaseUrl: DEFAULT_API_BASE }, (items) => {
      resolve(items.apiBaseUrl || DEFAULT_API_BASE);
    });
  });
}

chrome.runtime.onInstalled.addListener(() => {
  chrome.storage.sync.set({ apiBaseUrl: DEFAULT_API_BASE });
  chrome.action.setBadgeBackgroundColor({ color: "#ff9800" });
});

chrome.tabs.onRemoved.addListener((tabId) => {
  if (currentDetection && currentDetection.tabId === tabId) {
    currentDetection = null;
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "YAD2_URL_DETECTED") {
    currentDetection = {
      ...message.payload,
      tabId: sender.tab ? sender.tab.id : null,
      detectedAt: Date.now(),
    };
    chrome.action.setBadgeText({ text: "ON", tabId: currentDetection.tabId });
    sendResponse({ ok: true });
    return false;
  }

  if (message.type === "GET_DETECTION") {
    sendResponse({ detection: currentDetection });
    return false;
  }

  if (message.type === "AUTHENTICATE") {
    handleAuthentication(message.payload)
      .then((result) => sendResponse({ ok: true, ...result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true; // keep channel open for async response
  }

  if (message.type === "REGISTER_USER") {
    handleRegistration(message.payload)
      .then((result) => sendResponse({ ok: true, data: result }))
      .catch((error) => sendResponse({ ok: false, error: error.message }));
    return true; // keep channel open for async response
  }

  if (message.type === "GET_SETTINGS") {
    getApiBaseUrl().then((url) => sendResponse({ apiBaseUrl: url }));
    return true;
  }

  if (message.type === "SET_SETTINGS") {
    chrome.storage.sync.set({ apiBaseUrl: message.payload.apiBaseUrl || DEFAULT_API_BASE }, () => {
      sendResponse({ ok: true });
    });
    return true;
  }

  return false;
});

async function handleAuthentication(authData) {
  const apiBaseUrl = await getApiBaseUrl();
  const payload = {
    username: authData.username,
    password: authData.password,
  };

  const response = await fetch(`${apiBaseUrl}/auth`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok) {
    const errorMessage = data?.detail || data?.message || "Authentication failed";
    throw new Error(errorMessage);
  }

  return data;
}

async function handleRegistration(formData) {
  if (!currentDetection) {
    throw new Error("No Yad2 search detected yet.");
  }

  const apiBaseUrl = await getApiBaseUrl();
  const payload = {
    username: formData.username,
    label: formData.label || null,
    search_url: currentDetection.url,
    query_params: currentDetection.params,
  };

  const response = await fetch(`${apiBaseUrl}/users/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!response.ok) {
    const errorMessage = data?.detail || data?.message || "Registration failed";
    throw new Error(errorMessage);
  }

  await storeRegistration(data, payload);

  return data;
}

async function storeRegistration(result, payload) {
  return new Promise((resolve) => {
    chrome.storage.sync.get({ registrations: {} }, (items) => {
      const registrations = items.registrations;
      registrations[result.user_id] = {
        userId: result.user_id,
        preferenceId: result.preference_id,
        telegramLink: result.telegram_deep_link,
        username: payload.username,
        registeredAt: new Date().toISOString(),
      };

      chrome.storage.sync.set({ registrations }, () => {
        resolve();
      });
    });
  });
}
