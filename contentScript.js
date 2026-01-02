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

    // Try multiple click methods to ensure menu opens
    // Method 1: Native mouse events
    const clickEvent = new MouseEvent('click', {
      view: window,
      bubbles: true,
      cancelable: true,
      buttons: 1
    });
    menuBtn.dispatchEvent(clickEvent);

    await sleep(800);

    // Check if menu appeared, if not try again with different method
    let menuAppeared = document.querySelectorAll('[role="menu"]').length > 0 ||
                       Array.from(document.querySelectorAll('*')).some(el =>
                         el.textContent.includes('Share') && el.textContent.includes('Delete')
                       );

    if (!menuAppeared) {
      log("Menu didn't appear, trying mousedown + mouseup");
      menuBtn.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true }));
      await sleep(50);
      menuBtn.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true }));
      await sleep(800);
    }

    // SUPER aggressive debug: Log EVERYTHING visible
    const allText = Array.from(document.querySelectorAll('*'))
      .filter(el => {
        const rect = el.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0 && el.textContent.trim().length > 0;
      })
      .map(el => el.textContent.trim())
      .filter((text, index, self) => self.indexOf(text) === index) // unique
      .filter(text => text.length < 50)
      .sort();

    log("ALL unique visible text on page (first 100):", allText.slice(0, 100));

    // Check if Share, Rename, Delete are in the page at all
    const hasShare = allText.some(t => t.toLowerCase().includes('share'));
    const hasRename = allText.some(t => t.toLowerCase().includes('rename'));
    const hasDelete = allText.some(t => t.toLowerCase().includes('delete'));

    log(`Text found: Share=${hasShare}, Rename=${hasRename}, Delete=${hasDelete}`);

    let deleteBtn = null;

    // Search for delete with case-insensitive approach
    const allElements = Array.from(document.querySelectorAll('*'));

    for (const el of allElements) {
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;

      const text = el.textContent.trim().toLowerCase();

      if (text === 'delete' || (text.includes('delete') && text.length < 30)) {
        log(`FOUND element with delete: ${el.tagName}.${el.className} text="${el.textContent.trim()}"`);
        deleteBtn = el;
        break;
      }
    }

    if (!deleteBtn) {
      log("CRITICAL: Could not find delete. Trying to find the menu itself...");

      // Try to find elements that appeared recently (high z-index, fixed/absolute)
      const recentlyAppeared = Array.from(document.querySelectorAll('*'))
        .filter(el => {
          const rect = el.getBoundingClientRect();
          const style = window.getComputedStyle(el);
          const zIndex = parseInt(style.zIndex);
          return rect.width > 100 &&
                 (style.position === 'fixed' || style.position === 'absolute') &&
                 zIndex > 100;
        })
        .sort((a, b) => parseInt(window.getComputedStyle(b).zIndex) - parseInt(window.getComputedStyle(a).zIndex));

      log(`Found ${recentlyAppeared.length} high-z-index positioned elements`);

      if (recentlyAppeared.length > 0) {
        for (let i = 0; i < Math.min(3, recentlyAppeared.length); i++) {
          const el = recentlyAppeared[i];
          log(`Element #${i}: ${el.tagName} z-index=${window.getComputedStyle(el).zIndex} class="${el.className.substring(0, 50)}" text="${el.textContent.substring(0, 100)}"`);
        }
      }

      throw new Error("Could not find Delete option - menu may not have opened");
    }

    log("Found delete element:", deleteBtn.tagName, deleteBtn.className);

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
