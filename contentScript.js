(() => {
  // Prevent duplicate injection
  if (window.__mgpc_bulk_select_injected__) return;
  window.__mgpc_bulk_select_injected__ = true;

  const STATE = {
    selected: new Set(),
    deleting: false,
    authHeaders: {},
  };

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const log = (...args) => console.log("[CGPT Bulk Delete]", ...args);

  // Intercept fetch to capture authentication headers
  const originalFetch = window.fetch;
  window.fetch = function(...args) {
    const [url, options] = args;

    // Capture auth headers from any backend-api request
    if (typeof url === 'string' && url.includes('/backend-api/')) {
      if (options?.headers) {
        // Store important auth headers
        const headers = options.headers;
        if (headers['Authorization'] || headers['authorization']) {
          STATE.authHeaders['Authorization'] = headers['Authorization'] || headers['authorization'];
        }
        if (headers['Cookie'] || headers['cookie']) {
          STATE.authHeaders['Cookie'] = headers['Cookie'] || headers['cookie'];
        }
        if (headers['X-Authorization'] || headers['x-authorization']) {
          STATE.authHeaders['X-Authorization'] = headers['X-Authorization'] || headers['x-authorization'];
        }

        log("Captured auth headers from ChatGPT request");
      }
    }

    return originalFetch.apply(this, args);
  };

  function isChatLink(a) {
    if (!(a instanceof HTMLAnchorElement)) return false;
    const href = a.getAttribute("href") || "";
    return /^\/(c|chat)\//.test(href);
  }

  function findSidebar() {
    const a =
      document.querySelector("a[href^='/c/']") ||
      document.querySelector("a[href^='/chat/']");
    if (!a) return null;

    return (
      a.closest("nav") ||
      a.closest("aside") ||
      a.closest("[role='navigation']") ||
      a.closest("div")
    );
  }

  function getChatAnchors(sidebar) {
    return Array.from(sidebar.querySelectorAll("a")).filter(isChatLink);
  }

  function extractChatId(href) {
    const match = href.match(/\/(c|chat)\/([a-f0-9-]+)/);
    return match ? match[2] : null;
  }

  // ---------- UI ----------
  function ensureBulkBar(sidebar) {
    if (sidebar.querySelector("#cgpt-bulkbar")) return;

    const bar = document.createElement("div");
    bar.id = "cgpt-bulkbar";
    bar.style.position = "sticky";
    bar.style.top = "0";
    bar.style.zIndex = "9999";
    bar.style.display = "flex";
    bar.style.gap = "8px";
    bar.style.alignItems = "center";
    bar.style.padding = "8px";
    bar.style.margin = "6px";
    bar.style.borderRadius = "12px";
    bar.style.background = "rgba(0,0,0,0.06)";
    bar.style.backdropFilter = "blur(4px)";
    bar.style.fontFamily =
      "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial";

    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "Delete Selected";
    deleteBtn.style.border = "none";
    deleteBtn.style.background = "rgb(220, 38, 38)";
    deleteBtn.style.color = "white";
    deleteBtn.style.borderRadius = "10px";
    deleteBtn.style.padding = "8px 16px";
    deleteBtn.style.cursor = "pointer";
    deleteBtn.style.fontSize = "13px";
    deleteBtn.style.fontWeight = "600";
    deleteBtn.onclick = async () => {
      if (STATE.deleting) return;
      if (STATE.selected.size === 0) {
        alert("Please select at least one chat to delete.");
        return;
      }
      const ok = confirm(
        `Delete ${STATE.selected.size} selected chat(s)? This cannot be undone.`
      );
      if (!ok) return;
      await bulkDeleteSelected(sidebar);
    };

    const count = document.createElement("div");
    count.className = "count";
    count.style.marginLeft = "auto";
    count.style.fontSize = "13px";
    count.style.fontWeight = "500";
    count.style.opacity = "0.9";
    count.textContent = "0 selected";

    bar.append(deleteBtn, count);
    sidebar.prepend(bar);
  }

  function updateCount(sidebar) {
    const bar = sidebar.querySelector("#cgpt-bulkbar");
    if (!bar) return;
    const countEl = bar.querySelector(".count");
    if (countEl) countEl.textContent = `${STATE.selected.size} selected`;
  }

  function ensureCheckboxes(sidebar) {
    const anchors = getChatAnchors(sidebar);

    for (const a of anchors) {
      const href = a.getAttribute("href");
      if (!href) continue;

      if (a.dataset.cgptBulkProcessed === "1") continue;
      a.dataset.cgptBulkProcessed = "1";

      a.style.position = "relative";
      a.style.paddingLeft = "30px";

      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.className = "cgpt-bulk-checkbox";
      cb.checked = STATE.selected.has(href);

      cb.style.position = "absolute";
      cb.style.left = "10px";
      cb.style.top = "50%";
      cb.style.transform = "translateY(-50%)";
      cb.style.width = "16px";
      cb.style.height = "16px";
      cb.style.cursor = "pointer";
      cb.style.zIndex = "10";

      cb.addEventListener("click", (e) => {
        e.stopPropagation();
      }, true);

      cb.addEventListener("change", (e) => {
        e.stopPropagation();
        if (cb.checked) {
          STATE.selected.add(href);
        } else {
          STATE.selected.delete(href);
        }
        updateCount(sidebar);
      });

      a.prepend(cb);
    }

    updateCount(sidebar);
  }

  // ---------- API-based deletion ----------
  async function deleteConversationAPI(chatId) {
    log(`Deleting chat via API: ${chatId}`);

    // Build headers with auth
    const headers = {
      'Content-Type': 'application/json',
      ...STATE.authHeaders
    };

    const baseUrl = window.location.origin;
    const apiUrl = `${baseUrl}/backend-api/conversation/${chatId}`;

    try {
      const response = await fetch(apiUrl, {
        method: 'PATCH',
        headers: headers,
        credentials: 'include', // Important: include cookies
        body: JSON.stringify({
          is_visible: false
        })
      });

      if (!response.ok) {
        throw new Error(`API returned ${response.status}: ${response.statusText}`);
      }

      log(`Successfully deleted chat ${chatId}`);
      return true;
    } catch (error) {
      log(`Failed to delete chat ${chatId}:`, error.message);
      throw error;
    }
  }

  async function bulkDeleteSelected(sidebar) {
    if (STATE.selected.size === 0) return;

    // Check if we have auth headers
    if (Object.keys(STATE.authHeaders).length === 0) {
      alert("Authentication not ready. Please:\n1. Click on any chat first\n2. Then try deleting\n\nThis captures the auth tokens needed.");
      return;
    }

    STATE.deleting = true;

    const bar = sidebar.querySelector("#cgpt-bulkbar");
    const deleteBtn = bar?.querySelector("button");
    const originalText = deleteBtn?.textContent;

    try {
      const hrefs = Array.from(STATE.selected);
      const total = hrefs.length;
      let successCount = 0;
      let failCount = 0;

      for (let i = 0; i < hrefs.length; i++) {
        const href = hrefs[i];
        const chatId = extractChatId(href);

        if (!chatId) {
          log(`Could not extract chat ID from ${href}`);
          failCount++;
          STATE.selected.delete(href);
          updateCount(sidebar);
          continue;
        }

        // Update button to show progress
        if (deleteBtn) {
          deleteBtn.textContent = `Deleting ${i + 1}/${total}...`;
          deleteBtn.style.opacity = "0.7";
        }

        try {
          await deleteConversationAPI(chatId);
          successCount++;
          STATE.selected.delete(href);
          updateCount(sidebar);

          // Small delay between requests
          await sleep(300);
        } catch (error) {
          log(`Failed to delete chat ${i + 1}/${total}:`, error.message);
          failCount++;
        }
      }

      // Show result message
      if (deleteBtn) {
        const message = failCount > 0
          ? `✓ Deleted ${successCount}, ${failCount} failed`
          : `✓ Deleted ${successCount}!`;
        deleteBtn.textContent = message;

        setTimeout(() => {
          if (deleteBtn) {
            deleteBtn.textContent = originalText || "Delete Selected";
            deleteBtn.style.opacity = "1";
          }
        }, 3000);
      }

      if (successCount > 0) {
        log(`Bulk delete complete: ${successCount} deleted, ${failCount} failed`);
        // Refresh the page to update the sidebar
        setTimeout(() => window.location.reload(), 1500);
      }
    } finally {
      STATE.deleting = false;
      if (deleteBtn && deleteBtn.textContent.includes("Deleting")) {
        deleteBtn.textContent = originalText || "Delete Selected";
        deleteBtn.style.opacity = "1";
      }
    }
  }

  // ---------- Boot ----------
  function bootOnce() {
    const sidebar = findSidebar();
    if (!sidebar) return false;

    ensureBulkBar(sidebar);
    ensureCheckboxes(sidebar);

    let scheduled = false;
    const scheduleUpdate = () => {
      if (scheduled) return;
      scheduled = true;
      requestAnimationFrame(() => {
        scheduled = false;
        const sb = findSidebar();
        if (!sb) return;
        ensureBulkBar(sb);
        ensureCheckboxes(sb);
      });
    };

    const sidebarObserver = new MutationObserver(scheduleUpdate);
    sidebarObserver.observe(sidebar, { childList: true, subtree: true });

    log("API-based Bulk Delete Active!");
    return true;
  }

  let attempts = 0;
  const timer = setInterval(() => {
    attempts++;
    if (bootOnce() || attempts > 20) clearInterval(timer);
  }, 500);
})();
