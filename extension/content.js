(function () {
  const TARGET_HOST = "www.yad2.co.il";
  const TARGET_PATH_PREFIX = "/realestate";
  let lastNotifiedUrl = null;

  function isRelevant(url) {
    return url.hostname === TARGET_HOST && url.pathname.startsWith(TARGET_PATH_PREFIX);
  }

  function buildParams(url) {
    const params = {};
    for (const [key, value] of url.searchParams.entries()) {
      if (params[key]) {
        if (Array.isArray(params[key])) {
          params[key].push(value);
        } else {
          params[key] = [params[key], value];
        }
      } else {
        params[key] = value;
      }
    }
    return params;
  }

  function notifyIfRelevant() {
    try {
      const currentUrl = new URL(window.location.href);
      if (!isRelevant(currentUrl)) {
        lastNotifiedUrl = null;
        return;
      }

      if (currentUrl.toString() === lastNotifiedUrl) {
        return;
      }

      const params = buildParams(currentUrl);
      lastNotifiedUrl = currentUrl.toString();

      chrome.runtime.sendMessage({
        type: "YAD2_URL_DETECTED",
        payload: {
          url: currentUrl.toString(),
          params,
        },
      });
    } catch (error) {
      console.error("Yad2 monitor content script error", error);
    }
  }

  const observer = new MutationObserver(() => {
    notifyIfRelevant();
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
  });

  window.addEventListener("popstate", notifyIfRelevant);
  window.addEventListener("hashchange", notifyIfRelevant);

  notifyIfRelevant();
})();
