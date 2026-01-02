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
    log("Attempting to delete chat:", anchor.getAttribute("href"));

    anchor.scrollIntoView({ block: "center" });
    await sleep(400);

    // Try to find a menu button in the row
    const row = anchor.closest("li") || anchor.parentElement;
    if (!row) {
      log("ERROR: Could not find row container");
      throw new Error("Could not find row container");
    }

    // Find menu button with multiple strategies
    let menuBtn =
      row.querySelector("button[aria-haspopup='menu']") ||
      row.querySelector("button[data-testid='more-options']") ||
      Array.from(row.querySelectorAll("button")).find((b) => {
        const label = (b.getAttribute("aria-label") || "").toLowerCase();
        return label.includes("more") || label.includes("menu") || label.includes("options");
      });

    if (!menuBtn) {
      log("ERROR: Could not find menu button. Row HTML:", row.outerHTML.substring(0, 200));
      throw new Error("Could not find menu button");
    }

    log("Clicking menu button");
    menuBtn.click();
    await sleep(700);

    // Debug: Discover what menu structure ChatGPT is using
    const possibleMenus = [
      ...Array.from(document.body.querySelectorAll("[role='menu']")),
      ...Array.from(document.body.querySelectorAll("[role='dialog']")),
      ...Array.from(document.body.querySelectorAll("div[data-radix-popper-content-wrapper]")),
      ...Array.from(document.body.querySelectorAll("div[data-headlessui-state='open']")),
      ...Array.from(document.body.querySelectorAll("[class*='menu']")),
      ...Array.from(document.body.querySelectorAll("[class*='popover']")),
      ...Array.from(document.body.querySelectorAll("[class*='dropdown']"))
    ];

    log(`Found ${possibleMenus.length} potential menu containers`);

    // Find recently visible elements (appeared in last second)
    const recentElements = Array.from(document.body.querySelectorAll("*")).filter(el => {
      const rect = el.getBoundingClientRect();
      return rect.width > 50 && rect.height > 20 &&
             window.getComputedStyle(el).position !== 'static' &&
             el.textContent.length > 0 && el.textContent.length < 100;
    });

    log(`Potential menu items (by visibility):`, recentElements.slice(0, 20).map(el =>
      `${el.tagName} "${el.textContent.trim().substring(0, 30)}"`
    ));

    // Try to find delete option with maximum flexibility
    let deleteBtn = null;

    // Strategy 1: Look for any element with "delete" text that became visible
    const deleteElements = recentElements.filter(el =>
      normalizeText(el.textContent).includes("delete")
    );

    log(`Found ${deleteElements.length} elements containing "delete":`,
        deleteElements.map(el => `${el.tagName}.${el.className} "${el.textContent.trim()}"`));

    if (deleteElements.length > 0) {
      // Prefer clickable elements (a, button, or elements with click handlers)
      deleteBtn = deleteElements.find(el =>
        el.tagName === 'BUTTON' || el.tagName === 'A' || el.onclick || el.getAttribute('role') === 'menuitem'
      ) || deleteElements[0];
    }

    // Strategy 2: Classic selectors
    if (!deleteBtn) {
      deleteBtn =
        findButtonByText(document.body, ["Delete", "Delete chat", "Remove"]) ||
        Array.from(document.body.querySelectorAll("[role='menuitem']")).find(el =>
          normalizeText(el.textContent).includes("delete")
        );
    }

    if (!deleteBtn) {
      log("ERROR: Could not find Delete option after trying all strategies");
      throw new Error("Could not find Delete option");
    }

    log("Found delete button:", deleteBtn.tagName, deleteBtn.className, `"${deleteBtn.textContent.trim()}"`);

    log("Clicking delete button");
    deleteBtn.click();
    await sleep(600);

    // Debug: Log all visible buttons
    const allButtons = Array.from(document.body.querySelectorAll("button"));
    const visibleButtons = allButtons.filter(b => {
      const rect = b.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    });
    log(`Found ${visibleButtons.length} visible buttons after clicking delete`);

    // Find confirmation button
    const confirm =
      findButtonByText(document.body, ["Delete", "Confirm"]) ||
      Array.from(document.body.querySelectorAll("button")).find((b) =>
        normalizeText(b.textContent) === "delete" || normalizeText(b.textContent) === "confirm"
      ) ||
      // Look for red/danger buttons (delete confirmations are usually red)
      Array.from(document.body.querySelectorAll("button")).find((b) => {
        const text = normalizeText(b.textContent);
        const style = window.getComputedStyle(b);
        const bgColor = style.backgroundColor;
        return (text.includes("delete") || text.includes("confirm")) &&
               (bgColor.includes("rgb(220") || bgColor.includes("red"));
      });

    if (!confirm) {
      log("ERROR: Could not find confirm Delete button. Visible buttons:",
          visibleButtons.slice(0, 10).map(b => `"${b.textContent.trim()}"`).join(", "));
      throw new Error("Could not find confirm Delete button");
    }

    log("Clicking confirm button:", confirm.textContent.trim());
    confirm.click();
    await sleep(800);
    log("Chat deleted successfully");
  }

  async function bulkDeleteSelected(sidebar) {
    if (STATE.selected.size === 0) return;
    STATE.deleting = true;

    const bar = sidebar.querySelector("#cgpt-bulkbar");
    const deleteBtn = bar?.querySelector("button");
    const originalText = deleteBtn?.textContent;

    try {
      const hrefs = Array.from(STATE.selected);
      const total = hrefs.length;

      for (let i = 0; i < hrefs.length; i++) {
        const href = hrefs[i];

        // Update button to show progress
        if (deleteBtn) {
          deleteBtn.textContent = `Deleting ${i + 1}/${total}...`;
          deleteBtn.style.opacity = "0.7";
        }

        // Re-find anchor because list re-renders
        const a = sidebar.querySelector(`a[href='${CSS.escape(href)}']`);
        if (!a) {
          STATE.selected.delete(href);
          updateCount(sidebar);
          continue;
        }

        try {
          await deleteChatByAnchor(a);
          STATE.selected.delete(href);
          updateCount(sidebar);
        } catch (error) {
          log(`Failed to delete chat ${i + 1}/${total}:`, error.message);
          // Continue with next deletion even if one fails
        }

        await sleep(350);
      }

      // Show success message
      if (deleteBtn) {
        deleteBtn.textContent = "✓ Deleted!";
        setTimeout(() => {
          if (deleteBtn) {
            deleteBtn.textContent = originalText || "Delete selected";
            deleteBtn.style.opacity = "1";
          }
        }, 2000);
      }
    } finally {
      STATE.deleting = false;
      if (deleteBtn && deleteBtn.textContent.includes("Deleting")) {
        deleteBtn.textContent = originalText || "Delete selected";
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
