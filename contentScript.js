(() => {
  // Prevent the content script running twice on the same page (ChatGPT is a SPA)
  if (window.__mgpc_bulk_select_injected__) return;
  window.__mgpc_bulk_select_injected__ = true;

  const STATE = {
    selected: new Set(),
    deleting: false,
  };

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const log = (...args) => console.log("[CGPT Bulk Delete]", ...args);

  function isChatLink(a) {
    if (!(a instanceof HTMLAnchorElement)) return false;
    const href = a.getAttribute("href") || "";
    return /^\/(c|chat)\//.test(href);
  }

  function findSidebar() {
    // Find any conversation link, then walk up to a likely container
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
    bar.style.gap = "8px";
    bar.style.alignItems = "center";
    bar.style.padding = "8px";
    bar.style.margin = "6px";
    bar.style.borderRadius = "12px";
    bar.style.background = "rgba(0,0,0,0.06)";
    bar.style.backdropFilter = "blur(4px)";
    bar.style.fontFamily =
      "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial";

    const mkBtn = (label) => {
      const b = document.createElement("button");
      b.textContent = label;
      b.style.border = "1px solid rgba(0,0,0,0.12)";
      b.style.background = "white";
      b.style.borderRadius = "10px";
      b.style.padding = "6px 10px";
      b.style.cursor = "pointer";
      b.style.fontSize = "12px";
      return b;
    };

    const selectAllBtn = mkBtn("Select all");
    selectAllBtn.onclick = () => selectAll(sidebar);

    const selectNoneBtn = mkBtn("Select none");
    selectNoneBtn.onclick = () => selectNone(sidebar);

    const deleteBtn = mkBtn("Delete selected");
    deleteBtn.style.borderColor = "rgba(220, 38, 38, 0.35)";
    deleteBtn.onclick = async () => {
      if (STATE.deleting) return;
      const ok = confirm(
        `Delete ${STATE.selected.size} selected chat(s)? This cannot be undone.`
      );
      if (!ok) return;
      await bulkDeleteSelected(sidebar);
    };

    const count = document.createElement("div");
    count.className = "count";
    count.style.marginLeft = "auto";
    count.style.fontSize = "12px";
    count.style.opacity = "0.8";
    count.textContent = "0 selected";

    bar.append(selectAllBtn, selectNoneBtn, deleteBtn, count);
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

      // Prevent endless reinjection / DOM churn
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

      // Stop propagation to prevent parent <a> navigation, but allow checkbox to toggle
      cb.addEventListener("click", (e) => {
        e.stopPropagation();
        // Don't preventDefault - we want the checkbox to toggle naturally
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

  function selectAll(sidebar) {
    for (const a of getChatAnchors(sidebar)) {
      const href = a.getAttribute("href");
      if (!href) continue;
      STATE.selected.add(href);
      const cb = a.querySelector("input.cgpt-bulk-checkbox");
      if (cb) cb.checked = true;
    }
    updateCount(sidebar);
  }

  function selectNone(sidebar) {
    STATE.selected.clear();
    for (const a of getChatAnchors(sidebar)) {
      const cb = a.querySelector("input.cgpt-bulk-checkbox");
      if (cb) cb.checked = false;
    }
    updateCount(sidebar);
  }

  // ---------- Delete automation (best effort) ----------
  function normalizeText(s) {
    return (s || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  function findButtonByText(root, labels) {
    const want = labels.map(normalizeText);
    for (const b of Array.from(root.querySelectorAll("button"))) {
      const t = normalizeText(b.textContent);
      if (!t) continue;
      if (want.some((w) => t === w || t.includes(w))) return b;
    }
    return null;
  }

  async function deleteChatByAnchor(anchor) {
    anchor.scrollIntoView({ block: "center" });
    await sleep(250);

    // Try to find a menu button in the row
    const row = anchor.closest("li") || anchor.parentElement;
    if (!row) throw new Error("Could not find row container");

    const menuBtn =
      row.querySelector("button[aria-haspopup='menu']") ||
      Array.from(row.querySelectorAll("button")).find((b) =>
        (b.getAttribute("aria-label") || "").toLowerCase().includes("more")
      );

    if (!menuBtn) throw new Error("Could not find menu button");

    menuBtn.click();
    await sleep(250);

    const deleteBtn =
      findButtonByText(document.body, ["Delete", "Delete chat", "Remove"]) ||
      Array.from(document.body.querySelectorAll("[role='menuitem']")).find((el) =>
        normalizeText(el.textContent).includes("delete")
      );

    if (!deleteBtn) throw new Error("Could not find Delete option");

    deleteBtn.click();
    await sleep(250);

    const confirm = findButtonByText(document.body, ["Delete", "Confirm"]);
    if (!confirm) throw new Error("Could not find confirm Delete button");

    confirm.click();
    await sleep(500);
  }

  async function bulkDeleteSelected(sidebar) {
    if (STATE.selected.size === 0) return;
    STATE.deleting = true;

    try {
      const hrefs = Array.from(STATE.selected);

      for (let i = 0; i < hrefs.length; i++) {
        const href = hrefs[i];

        // Re-find anchor because list re-renders
        const a = sidebar.querySelector(`a[href='${CSS.escape(href)}']`);
        if (!a) {
          STATE.selected.delete(href);
          updateCount(sidebar);
          continue;
        }

        await deleteChatByAnchor(a);
        STATE.selected.delete(href);
        updateCount(sidebar);

        await sleep(350);
      }
    } finally {
      STATE.deleting = false;
    }
  }

  // ---------- Boot ----------
  function bootOnce() {
    const sidebar = findSidebar();
    if (!sidebar) return false;

    ensureBulkBar(sidebar);
    ensureCheckboxes(sidebar);

    // Observe ONLY the sidebar, debounced
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

    log("Booted");
    return true;
  }

  let attempts = 0;
  const timer = setInterval(() => {
    attempts++;
    if (bootOnce() || attempts > 20) clearInterval(timer);
  }, 500);
})();
