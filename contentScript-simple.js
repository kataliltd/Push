(() => {
  // Prevent duplicate injection
  if (window.__mgpc_bulk_select_injected__) return;
  window.__mgpc_bulk_select_injected__ = true;

  const STATE = {
    selected: new Set(),
    currentIndex: 0,
  };

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const log = (...args) => console.log("[CGPT Bulk Delete]", ...args);

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

  // ---------- UI ----------
  function ensureBulkBar(sidebar) {
    if (sidebar.querySelector("#cgpt-bulkbar")) return;

    const bar = document.createElement("div");
    bar.id = "cgpt-bulkbar";
    bar.style.position = "sticky";
    bar.style.top = "0";
    bar.style.zIndex = "9999";
    bar.style.display = "flex";
    bar.style.flexDirection = "column";
    bar.style.gap = "8px";
    bar.style.padding = "12px";
    bar.style.margin = "6px";
    bar.style.borderRadius = "12px";
    bar.style.background = "rgba(220, 38, 38, 0.1)";
    bar.style.border = "2px solid rgb(220, 38, 38)";
    bar.style.fontFamily = "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial";

    const title = document.createElement("div");
    title.textContent = "📋 Bulk Delete Mode";
    title.style.fontSize = "14px";
    title.style.fontWeight = "700";
    title.style.color = "rgb(220, 38, 38)";

    const instructions = document.createElement("div");
    instructions.style.fontSize = "12px";
    instructions.style.color = "#666";
    instructions.style.lineHeight = "1.4";
    instructions.innerHTML = `
      <b>How to use:</b><br>
      1. Check chats you want to delete<br>
      2. Click "Highlight Next" to navigate<br>
      3. Manually click the ⋮ menu and delete<br>
      4. Repeat for each selected chat
    `;

    const controls = document.createElement("div");
    controls.style.display = "flex";
    controls.style.gap = "8px";
    controls.style.alignItems = "center";

    const highlightBtn = document.createElement("button");
    highlightBtn.textContent = "Highlight Next";
    highlightBtn.style.flex = "1";
    highlightBtn.style.border = "none";
    highlightBtn.style.background = "rgb(220, 38, 38)";
    highlightBtn.style.color = "white";
    highlightBtn.style.borderRadius = "8px";
    highlightBtn.style.padding = "8px 12px";
    highlightBtn.style.cursor = "pointer";
    highlightBtn.style.fontSize = "13px";
    highlightBtn.style.fontWeight = "600";
    highlightBtn.onclick = () => highlightNextSelected(sidebar);

    const clearBtn = document.createElement("button");
    clearBtn.textContent = "Clear All";
    clearBtn.style.border = "1px solid #ccc";
    clearBtn.style.background = "white";
    clearBtn.style.borderRadius = "8px";
    clearBtn.style.padding = "8px 12px";
    clearBtn.style.cursor = "pointer";
    clearBtn.style.fontSize = "12px";
    clearBtn.onclick = () => clearAll(sidebar);

    const count = document.createElement("div");
    count.className = "count";
    count.style.fontSize = "13px";
    count.style.fontWeight = "600";
    count.style.color = "rgb(220, 38, 38)";
    count.textContent = "0 selected";

    controls.append(highlightBtn, clearBtn);
    bar.append(title, instructions, controls, count);
    sidebar.prepend(bar);
  }

  function updateCount(sidebar) {
    const bar = sidebar.querySelector("#cgpt-bulkbar");
    if (!bar) return;
    const countEl = bar.querySelector(".count");
    if (countEl) {
      countEl.textContent = `${STATE.selected.size} selected`;
    }
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

  function clearAll(sidebar) {
    STATE.selected.clear();
    STATE.currentIndex = 0;
    for (const a of getChatAnchors(sidebar)) {
      const cb = a.querySelector("input.cgpt-bulk-checkbox");
      if (cb) cb.checked = false;
      a.style.background = "";
      a.style.outline = "";
    }
    updateCount(sidebar);
  }

  function highlightNextSelected(sidebar) {
    const selectedHrefs = Array.from(STATE.selected);

    if (selectedHrefs.length === 0) {
      alert("Please select some chats first!");
      return;
    }

    // Clear previous highlights
    for (const a of getChatAnchors(sidebar)) {
      a.style.background = "";
      a.style.outline = "";
    }

    // Get next href
    const href = selectedHrefs[STATE.currentIndex % selectedHrefs.length];
    STATE.currentIndex++;

    // Find and highlight the chat
    const anchor = sidebar.querySelector(`a[href='${CSS.escape(href)}']`);
    if (anchor) {
      anchor.style.background = "rgba(220, 38, 38, 0.2)";
      anchor.style.outline = "3px solid rgb(220, 38, 38)";
      anchor.style.outlineOffset = "-3px";

      anchor.scrollIntoView({ behavior: "smooth", block: "center" });

      log(`Highlighted chat ${STATE.currentIndex}/${selectedHrefs.length}: ${href}`);

      // Show toast
      showToast(`Chat ${STATE.currentIndex}/${selectedHrefs.length} - Now manually click the ⋮ menu and delete`);
    } else {
      STATE.selected.delete(href);
      updateCount(sidebar);
      highlightNextSelected(sidebar); // Try next one
    }
  }

  function showToast(message) {
    const existingToast = document.getElementById("cgpt-toast");
    if (existingToast) existingToast.remove();

    const toast = document.createElement("div");
    toast.id = "cgpt-toast";
    toast.textContent = message;
    toast.style.position = "fixed";
    toast.style.top = "20px";
    toast.style.left = "50%";
    toast.style.transform = "translateX(-50%)";
    toast.style.background = "rgb(220, 38, 38)";
    toast.style.color = "white";
    toast.style.padding = "12px 24px";
    toast.style.borderRadius = "8px";
    toast.style.fontSize = "14px";
    toast.style.fontWeight = "600";
    toast.style.zIndex = "99999";
    toast.style.boxShadow = "0 4px 12px rgba(0,0,0,0.3)";

    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = "opacity 0.3s";
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 3000);
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

    log("Manual-Assist Bulk Delete Mode Active!");
    return true;
  }

  let attempts = 0;
  const timer = setInterval(() => {
    attempts++;
    if (bootOnce() || attempts > 20) clearInterval(timer);
  }, 500);
})();
