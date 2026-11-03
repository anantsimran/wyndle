"use strict";

// Runs in Reading Desk's webview. VS Code renders Markdown and its Mermaid
// extension renders diagrams; this script handles marks, comments, and contents.
(() => {
  const host = acquireVsCodeApi();
  const names = ["yellow", "green", "red", "important-yellow", "important-green", "important-red", "done"];
  let state = null;
  let article = null;
  let selected = null;
  let tooLong = false;
  let important = false;
  let mode = "later";
  let color = "green";
  let toolbar, commentsPanel, list, count, search, kindFilter, dialog, dialogTitle, dialogText, dialogSave, toast, popover, addButton, importantButton, sidebarButton;
  let contentsSearch, contentsList, contents = [];
  const modeButtons = new Map();
  const colorButtons = new Map();
  let pendingDialog = null;
  let pendingSaveId = null;
  let saveTimer;
  let refreshTimer;

  function send(action, payload) { host.postMessage({ type: action, ...payload }); }

  function make(tag, className, label) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (label !== undefined) element.textContent = label;
    return element;
  }

  function notify(message) {
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => { toast.hidden = true; }, 2600);
  }

  function trackSave(mark) {
    pendingSaveId = mark.id;
    notify("Saving comment…");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(() => {
      if (pendingSaveId === mark.id) {
        pendingSaveId = null;
        notify("Save not confirmed. Check the Reading Desk sidebar.");
      }
    }, 6000);
  }

  function getSelectionAnchor() {
    const selection = window.getSelection();
    if (!article || !selection || selection.isCollapsed || !selection.rangeCount) return null;
    const range = selection.getRangeAt(0);
    if (!article.contains(range.startContainer) || !article.contains(range.endContainer)) return null;
    const before = document.createRange();
    before.selectNodeContents(article);
    before.setEnd(range.startContainer, range.startOffset);
    const start = before.toString().length;
    const quote = range.toString();
    if (!quote || quote.length > 2000) return null;
    const text = article.textContent || "";
    const end = start + quote.length;
    const block = range.startContainer.parentElement?.closest("[data-line]");
    return { quote, prefix: text.slice(Math.max(0, start - 48), start), suffix: text.slice(end, end + 48),
      position: start, line: Number(block?.getAttribute("data-line") || 0) };
  }

  function updateSelection() {
    const current = getSelectionAnchor();
    tooLong = (window.getSelection()?.toString().length || 0) > 2000;
    if (current) selected = current;
    else if (!toolbar?.contains(document.activeElement) && !dialog?.contains(document.activeElement)) selected = null;
    updateControls();
  }

  function newMark() {
    return { id: crypto.randomUUID(), kind: mode, color, important: mode === "highlight" && important,
      anchor: selected || { quote: "", prefix: "", suffix: "", position: 0, line: 0 },
      surface: "preview", note: "", resolved: false, resolutionComment: "", resolutionHistory: [], created: new Date().toISOString() };
  }

  function updateControls() {
    if (addButton) addButton.setAttribute("aria-disabled", tooLong || !selected?.quote ? "true" : "false");
    if (importantButton) importantButton.disabled = mode !== "highlight";
    for (const [kind, button] of modeButtons) button.setAttribute("aria-pressed", String(mode === kind));
    for (const [choice, button] of colorButtons) button.setAttribute("aria-pressed", String(color === choice));
  }

  /** Collapse or expand the sidebar and remember the choice for this reading pane. */
  function setSidebar(collapsed) {
    const layout = document.querySelector(".reading-desk-layout");
    if (collapsed) layout?.classList.add("reading-desk-collapsed");
    else layout?.classList.remove("reading-desk-collapsed");
    sidebarButton?.setAttribute("aria-pressed", String(!collapsed));
    host.setState?.({ ...(host.getState?.() || {}), sidebarCollapsed: collapsed });
    keepContentInline();
  }

  function modeButton(kind, label) {
    const button = make("button", "reading-desk-mode", label);
    button.type = "button";
    button.addEventListener("click", () => { mode = kind; updateControls(); });
    modeButtons.set(kind, button);
    return button;
  }

  function mount() {
    if (toolbar) return;
    toolbar = make("div", "reading-desk-toolbar");
    toolbar.setAttribute("role", "toolbar"); toolbar.setAttribute("aria-label", "Reading Desk");
    toolbar.addEventListener("pointerdown", event => {
      if (!event.target.closest?.("button")) return;
      const current = getSelectionAnchor();
      if (current) selected = current;
      event.preventDefault();
    });
    toolbar.append(make("span", "reading-desk-brand", "Reading Desk"));
    toolbar.append(modeButton("later", "↩ Later"), modeButton("review", "✓ Review"), modeButton("highlight", "Highlight"), modeButton("done", "Done"), make("span", "reading-desk-divider"));
    for (const choice of ["yellow", "green", "red"]) {
      const button = make("button", "reading-desk-color");
      button.type = "button"; button.title = `${choice} mark`;
      button.setAttribute("aria-label", `${choice} mark`);
      button.append(make("span", `reading-desk-dot ${choice}`));
      button.addEventListener("click", () => { color = choice; updateControls(); });
      colorButtons.set(choice, button);
      toolbar.append(button);
    }
    importantButton = make("button", "reading-desk-important", "★ Important");
    importantButton.type = "button"; importantButton.title = "Toggle important highlight";
    importantButton.setAttribute("aria-pressed", "false");
    importantButton.addEventListener("click", () => {
      important = !important; importantButton.setAttribute("aria-pressed", String(important)); updateControls();
    });
    toolbar.append(importantButton);
    addButton = make("button", "reading-desk-add", "+ Add mark");
    addButton.type = "button";
    addButton.addEventListener("pointerdown", event => {
      const current = getSelectionAnchor();
      if (current) selected = current;
      updateControls();
      event.preventDefault();
    });
    addButton.addEventListener("click", event => {
      event.stopPropagation();
      if (tooLong || !selected?.quote) { notify(tooLong ? "Select at most 2,000 characters." : "Select a passage first."); return; }
      const selection = window.getSelection();
      const bounds = selection?.rangeCount ? selection.getRangeAt(0).getBoundingClientRect() : null;
      editDialog(newMark(), "create", bounds);
    });
    toolbar.append(addButton);
    const marksButton = make("button", "", "☰ Comments");
    marksButton.type = "button";
    marksButton.title = "Find saved comments in the sidebar";
    marksButton.addEventListener("click", () => {
      setSidebar(false); commentsPanel.scrollIntoView({ block: "nearest" }); search.focus();
    });
    sidebarButton = make("button", "reading-desk-sidebar-toggle", "Sidebar");
    sidebarButton.type = "button"; sidebarButton.title = "Show or hide the Contents and comments sidebar";
    sidebarButton.addEventListener("click", () => setSidebar(!document.querySelector(".reading-desk-layout")?.classList.contains("reading-desk-collapsed")));
    toolbar.append(marksButton, sidebarButton);
    setSidebar(Boolean(host.getState?.()?.sidebarCollapsed));
    updateControls();

    commentsPanel = document.querySelector(".reading-desk-comments");
    const head = make("div", "reading-desk-comments-head");
    count = make("strong", "", "Saved comments");
    head.append(count);
    const filters = make("div", "reading-desk-filters");
    search = make("input"); search.type = "search"; search.placeholder = "Search comments and passages";
    search.setAttribute("aria-label", "Search comments and passages");
    search.addEventListener("input", renderMarks);
    kindFilter = make("select"); kindFilter.setAttribute("aria-label", "Filter comment type");
    for (const [value, label] of [["all", "All types"], ["later", "Return later"], ["review", "For review"], ["highlight", "Highlights"], ["done", "Done"]]) {
      const option = make("option", "", label); option.value = value; kindFilter.append(option);
    }
    kindFilter.addEventListener("change", renderMarks);
    filters.append(search, kindFilter);
    list = make("div", "reading-desk-list"); commentsPanel.append(head, filters, list);

    popover = make("aside", "reading-desk-popover"); popover.hidden = true;
    popover.setAttribute("aria-label", "Marked passage comment");
    dialog = make("div", "reading-desk-dialog"); dialog.hidden = true;
    dialog.setAttribute("role", "dialog");
    const box = make("div", "reading-desk-dialog-box");
    dialogTitle = make("label", "", "Comment"); dialogText = make("textarea");
    dialogText.maxLength = 5000; dialogText.id = "reading-desk-comment"; dialogTitle.htmlFor = dialogText.id;
    dialogTitle.id = "reading-desk-dialog-title"; dialog.setAttribute("aria-labelledby", dialogTitle.id);
    const actions = make("div", "reading-desk-dialog-actions");
    const cancel = make("button", "", "Cancel"); cancel.type = "button";
    cancel.addEventListener("click", () => { dialog.hidden = true; pendingDialog = null; });
    dialogSave = make("button", "reading-desk-save", "Save"); dialogSave.type = "button";
    dialogSave.addEventListener("click", () => {
      if (!pendingDialog) return;
      const mark = pendingDialog.mode === "create" ? pendingDialog.mark : state.marks.find(item => item.id === pendingDialog.id);
      const action = pendingDialog.mode === "create" ? "create" : "update";
      const payload = pendingDialog.mode === "create" ? { ...mark, note: dialogText.value } :
        pendingDialog.mode === "comment" ? { id: pendingDialog.id, note: dialogText.value } :
          { id: pendingDialog.id, resolved: true, resolutionComment: dialogText.value };
      send(action, payload);
      if (mark) {
        if (pendingDialog.mode === "create") { mark.note = dialogText.value; state.marks.unshift(mark); }
        if (pendingDialog.mode === "comment") mark.note = dialogText.value;
        if (pendingDialog.mode === "resolution") {
          mark.resolved = true; mark.resolvedAt = new Date().toISOString();
          mark.resolutionHistory = [...(mark.resolutionHistory || []), { at: mark.resolvedAt, comment: dialogText.value }];
          mark.resolutionComment = dialogText.value;
        }
      }
      const wasCreate = pendingDialog.mode === "create";
      dialog.hidden = true; pendingDialog = null;
      selected = null; updateControls(); renderMarks(); paint();
      if (wasCreate && mark) trackSave(mark);
      else notify("Saving to reviews.json…");
    });
    actions.append(cancel, dialogSave); box.append(dialogTitle, dialogText, actions); dialog.append(box);
    dialog.addEventListener("click", event => { if (event.target === dialog) { dialog.hidden = true; pendingDialog = null; } });
    dialog.addEventListener("keydown", event => { if (event.key === "Escape") { dialog.hidden = true; pendingDialog = null; } });
    toast = make("div", "reading-desk-toast"); toast.hidden = true; toast.setAttribute("role", "status");
    document.body.append(toolbar, popover, dialog, toast);
    document.addEventListener("selectionchange", updateSelection);
    document.addEventListener("keyup", updateSelection);
    document.addEventListener("mouseup", updateSelection);
    document.addEventListener("click", revealAtClick);
    document.addEventListener("click", openContentLink);
    contentsSearch = document.querySelector(".reading-desk-toc-search");
    contentsList = document.querySelector(".reading-desk-toc-list");
    contentsSearch?.addEventListener("input", buildContents);
    window.addEventListener("scroll", updateCurrentHeading, { passive: true });
    window.addEventListener("resize", keepContentInline);
  }

  function buildContents() {
    if (!article || !contentsList) return;
    contentsList.replaceChildren();
    const query = contentsSearch?.value.trim().toLocaleLowerCase() || "";
    contents = [...article.querySelectorAll("h1,h2,h3,h4,h5,h6")]
      .filter(heading => !heading.closest(".mermaid"))
      .map(heading => ({ heading, title: heading.textContent.trim() }));
    for (const { heading, title } of contents) {
      if (query && !title.toLocaleLowerCase().includes(query)) continue;
      const button = make("button", `level-${heading.tagName.slice(1)}`, title || "Untitled heading");
      button.type = "button";
      button.addEventListener("click", () => heading.scrollIntoView({ behavior: "smooth", block: "start" }));
      button._heading = heading;
      contentsList.append(button);
    }
    if (!contentsList.children.length) contentsList.append(make("div", "reading-desk-toc-empty", query ? "No matching headings" : "No headings"));
    updateCurrentHeading();
  }

  /** Keep document styles from floating headings or indexes over the sidebar: flow fixed elements, and sticky ones outside the article, inline. */
  function keepContentInline() {
    if (!article || typeof getComputedStyle !== "function") return;
    article.querySelectorAll(".reading-desk-inline").forEach(element => element.classList.remove("reading-desk-inline"));
    const bounds = article.getBoundingClientRect();
    for (const element of article.querySelectorAll("*")) {
      const { position } = getComputedStyle(element);
      if (position !== "fixed" && position !== "sticky") continue;
      const rect = element.getBoundingClientRect();
      if (position === "fixed" || rect.left < bounds.left - 1 || rect.right > bounds.right + 1) element.classList.add("reading-desk-inline");
    }
  }

  function updateCurrentHeading() {
    if (!contentsList || !contents.length) return;
    let active = contents[0].heading;
    for (const { heading } of contents) {
      if (heading.getBoundingClientRect().top <= 140) active = heading;
      else break;
    }
    for (const button of contentsList.querySelectorAll("button")) {
      if (button._heading === active) button.setAttribute("aria-current", "location");
      else button.removeAttribute("aria-current");
    }
  }

  function positionBeside(element, bounds) {
    const width = 340;
    element.style.left = `${Math.max(12, Math.min((bounds?.left || 12), window.innerWidth - width - 12))}px`;
    element.style.top = `${Math.max(12, Math.min((bounds?.bottom || 48) + 8, window.innerHeight - 260))}px`;
  }

  function revealAtClick(event) {
    if (!article?.contains(event.target) || event.target.closest?.("a,button") || !window.getSelection()?.isCollapsed) return;
    const caret = document.caretRangeFromPoint?.(event.clientX, event.clientY);
    let offset = -1;
    if (caret && article.contains(caret.startContainer)) {
      const before = document.createRange(); before.selectNodeContents(article);
      before.setEnd(caret.startContainer, caret.startOffset);
      offset = before.toString().length;
    }
    const text = article.textContent || "";
    const block = event.target.closest?.("[data-line]");
    const line = block ? Number(block.getAttribute("data-line")) : -1;
    const marks = state?.marks.filter(mark => {
      const found = bestMatch(text, mark.anchor);
      if (found) return found.start <= offset && offset < found.end;
      return mark.surface === "source" && line >= 0 && mark.anchor.line === line;
    }) || [];
    if (!marks.length) { popover.hidden = true; return; }
    showComments(marks, { left: event.clientX, bottom: event.clientY });
  }

  function showComments(marks, bounds) {
    popover.replaceChildren();
    for (const mark of marks) {
      const card = make("section", "reading-desk-inline-card");
      card.style.borderLeft = `3px solid ${({ green: "#62b885", red: "#e87768", yellow: "#e9c34c" })[mark.color || "green"]}`;
      card.append(make("strong", "", mark.kind === "highlight" ? `${mark.important ? "Important " : ""}highlight` : mark.kind === "later" ? "Return later" : mark.kind === "done" ? "Done" : "For review"));
      if (mark.note) card.append(make("p", "", mark.note));
      if (mark.resolutionComment) card.append(make("p", "reading-desk-resolution", `Previous resolution: ${mark.resolutionComment}`));
      const actions = make("div", "reading-desk-card-actions");
      const edit = make("button", "", mark.note ? "Edit comment" : "Add comment");
      edit.type = "button"; edit.addEventListener("click", () => editDialog(mark, "comment", bounds));
      actions.append(edit);
      if (mark.resolved) actions.append(staticLink("Reopen", "update", { id: mark.id, resolved: false }, () => { mark.resolved = false; popover.hidden = true; }));
      else {
        actions.append(staticLink("Resolve", "update", { id: mark.id, resolved: true, resolutionComment: "" }, () => { mark.resolved = true; popover.hidden = true; }));
        const resolve = make("button", "", "Resolve + comment");
        resolve.type = "button"; resolve.addEventListener("click", () => editDialog(mark, "resolution", bounds));
        actions.append(resolve);
      }
      card.append(actions); popover.append(card);
    }
    positionBeside(popover, bounds);
    popover.hidden = false;
  }

  function editDialog(mark, mode, bounds) {
    pendingDialog = { id: mark.id, mark, mode };
    dialogTitle.textContent = mode === "create" ? `${mark.kind === "later" ? "Return later" : mark.kind === "review" ? "For review" : mark.kind === "done" ? "Done" : "Highlight"} comment` : mode === "comment" ? "Comment" : "Resolve with comment";
    dialogText.value = mode === "comment" ? mark.note || "" : "";
    dialogSave.textContent = mode === "create" ? "Save comment" : mode === "comment" ? "Save comment" : "Resolve";
    dialog.hidden = false; popover.hidden = true;
    positionBeside(dialog, bounds);
    dialogText.focus();
  }

  function staticLink(label, actionName, payload, after) {
    const button = make("button", "", label); button.type = "button";
    button.addEventListener("click", () => { send(actionName, payload); after(); renderMarks(); paint(); notify("Saving to reviews.json…"); });
    return button;
  }

  function openContentLink(event) {
    if (!article?.contains(event.target)) return;
    const anchor = event.target.closest?.("a");
    if (!anchor) return;
    const href = anchor.getAttribute("href");
    if (!href) return;
    event.preventDefault(); event.stopPropagation();
    if (href.startsWith("#")) {
      try { document.getElementById(decodeURIComponent(href.slice(1)))?.scrollIntoView(); } catch {}
    } else send("openLink", { href });
  }

  function locate(mark) {
    if (!article) return;
    if (mark.anchor.quote) {
      const found = bestMatch(article.textContent || "", mark.anchor);
      const range = found && rangeFor(found.start, found.end);
      if (range) { range.startContainer.parentElement?.scrollIntoView({ behavior: "smooth", block: "center" }); return; }
    }
    const line = article.querySelector(`[data-line="${mark.anchor.line || 0}"]`);
    line?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function renderMarks() {
    if (!state || !list) return;
    list.replaceChildren();
    const query = search.value.trim().toLocaleLowerCase();
    const marks = [...state.marks].filter(mark =>
      (kindFilter.value === "all" || mark.kind === kindFilter.value) &&
      (!query || [mark.anchor.quote, mark.note, mark.resolutionComment,
        mark.kind === "later" ? "Return later" : mark.kind === "review" ? "For review" : mark.kind === "done" ? "Done" : "Highlight"]
        .some(value => String(value || "").toLocaleLowerCase().includes(query))))
      .sort((a, b) => String(b.created || "").localeCompare(String(a.created || "")));
    count.textContent = `Saved comments · ${marks.length}${marks.length === state.marks.length ? "" : ` of ${state.marks.length}`}`;
    if (!marks.length) { list.append(make("div", "reading-desk-empty", state.marks.length ? "No matching comments." : "Select a passage, then choose a mark.")); return; }
    for (const mark of marks) {
      const card = make("section", "reading-desk-card");
      card.style.borderLeft = `3px solid ${({ green: "#62b885", red: "#e87768", yellow: "#e9c34c" })[mark.color || "green"]}`;
      const head = make("div", "reading-desk-card-head");
      head.append(make("span", "", mark.kind === "highlight" ? `${mark.important ? "★ Important " : ""}${mark.color || "green"} highlight` : mark.kind === "later" ? "↩ Return later" : mark.kind === "done" ? "Done" : "✓ For review"),
        make("small", "", mark.resolved ? "Resolved" : "Open"));
      card.append(head);
      const quote = make("blockquote", "", mark.anchor.quote?.trim() || "Whole file"); card.append(quote);
      if (mark.note) card.append(make("p", "", mark.note));
      if (mark.resolutionComment) card.append(make("p", "reading-desk-resolution", `${mark.resolved ? "Resolution" : "Previous resolution"}: ${mark.resolutionComment}`));
      if (mark.resolutionHistory?.length > 1) {
        const history = make("details", "reading-desk-history");
        history.append(make("summary", "", `${mark.resolutionHistory.length} resolution events`));
        for (const event of mark.resolutionHistory) {
          const date = event.at ? new Date(event.at).toLocaleDateString() : "Earlier";
          history.append(make("p", "", `${date}: ${event.comment || "Resolved without comment"}`));
        }
        card.append(history);
      }
      const controls = make("div", "reading-desk-card-actions");
      const go = make("button", "", "Go to"); go.type = "button"; go.addEventListener("click", () => locate(mark)); controls.append(go);
      const comment = make("button", "", mark.note ? "Edit comment" : "Add comment");
      comment.type = "button"; comment.addEventListener("click", () => editDialog(mark, "comment")); controls.append(comment);
      if (mark.kind === "highlight") {
        controls.append(staticLink(mark.important ? "Regular" : "★ Important", "update", { id: mark.id, important: !mark.important }, () => { mark.important = !mark.important; }));
      }
      if (mark.resolved) {
        controls.append(staticLink("Reopen", "update", { id: mark.id, resolved: false }, () => { mark.resolved = false; }));
      } else {
        controls.append(staticLink("Resolve", "update", { id: mark.id, resolved: true, resolutionComment: "" }, () => {
          mark.resolved = true; mark.resolvedAt = new Date().toISOString();
          mark.resolutionComment = "";
          mark.resolutionHistory = [...(mark.resolutionHistory || []), { at: mark.resolvedAt, comment: "" }];
        }));
        const resolveComment = make("button", "", "Resolve + comment");
        resolveComment.type = "button"; resolveComment.addEventListener("click", () => editDialog(mark, "resolution")); controls.append(resolveComment);
      }
      controls.append(staticLink("Delete", "delete", { id: mark.id }, () => { state.marks = state.marks.filter(item => item.id !== mark.id); }));
      card.append(controls); list.append(card);
    }
  }

  function bestMatch(text, anchor) {
    if (!anchor?.quote) return null;
    let at = -1, best = null;
    while ((at = text.indexOf(anchor.quote, at + 1)) !== -1) {
      const before = text.slice(Math.max(0, at - (anchor.prefix || "").length), at);
      const after = text.slice(at + anchor.quote.length, at + anchor.quote.length + (anchor.suffix || "").length);
      const hasContext = Boolean(anchor.prefix || anchor.suffix);
      const matchedContext = (anchor.prefix && before === anchor.prefix) || (anchor.suffix && after === anchor.suffix);
      if (hasContext && !matchedContext) continue;
      const score = (before === (anchor.prefix || "") ? 100 : 0) + (after === (anchor.suffix || "") ? 100 : 0) - Math.abs(at - (anchor.position || 0)) / 100;
      if (!best || score > best.score) best = { start: at, end: at + anchor.quote.length, score };
    }
    return best;
  }

  function rangeFor(start, end) {
    const walker = document.createTreeWalker(article, NodeFilter.SHOW_TEXT);
    let node, offset = 0, first = null, last = null;
    while ((node = walker.nextNode())) {
      const next = offset + node.textContent.length;
      if (!first && start < next) first = [node, start - offset];
      if (first && end <= next) { last = [node, end - offset]; break; }
      offset = next;
    }
    if (!first || !last) return null;
    const range = document.createRange(); range.setStart(...first); range.setEnd(...last); return range;
  }

  function paint() {
    if (!article || !state) return;
    for (const name of names) CSS.highlights?.delete(`reading-desk-${name}`);
    article.querySelectorAll(".reading-desk-source-line").forEach(element => {
      element.classList.remove("reading-desk-source-line");
      element.style.removeProperty("--reading-desk-line-color");
    });
    const groups = new Map(names.map(name => [name, []]));
    const text = article.textContent || "";
    for (const mark of state.marks) {
      if (mark.resolved) continue;
      const found = bestMatch(text, mark.anchor);
      const range = found && rangeFor(found.start, found.end);
      if (!range && mark.surface === "source") {
        const block = article.querySelector(`[data-line="${mark.anchor.line || 0}"]`);
        if (block) {
          block.classList.add("reading-desk-source-line");
          block.style.setProperty("--reading-desk-line-color", ({ green: "#62b88555", red: "#e8776855", yellow: "#e9c34c55" })[mark.color || "green"]);
        }
        continue;
      }
      if (!range) continue;
      const key = mark.kind === "done" ? "done" : `${mark.important ? "important-" : ""}${mark.color || "green"}`;
      groups.get(key)?.push(range);
    }
    if (typeof Highlight !== "undefined" && CSS.highlights) for (const [name, ranges] of groups) {
      if (ranges.length) CSS.highlights.set(`reading-desk-${name}`, new Highlight(...ranges));
    }
  }

  function refresh() {
    const data = document.getElementById("reading-desk-data");
    const body = document.querySelector(".markdown-body");
    if (!data || !body) return;
    try { state = JSON.parse(data.getAttribute("data-state") || ""); } catch { return; }
    article = body;
    mount(); keepContentInline(); buildContents(); renderMarks(); paint(); updateControls();
    if (state.reveal) setTimeout(() => revealMark(state.reveal), 100);
    if (state.fragment) setTimeout(() => scrollToFragment(state.fragment), 100);
  }

  function scrollToFragment(fragment) {
    document.getElementById(fragment)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function revealMark(id) {
    const mark = state?.marks.find(item => item.id === id);
    if (!mark) return;
    locate(mark);
    setTimeout(() => {
      const found = bestMatch(article.textContent || "", mark.anchor);
      const range = found && rangeFor(found.start, found.end);
      const block = article.querySelector(`[data-line="${mark.anchor.line || 0}"]`);
      showComments([mark], range?.getBoundingClientRect() || block?.getBoundingClientRect() || { left: 12, bottom: 48 });
    }, 350);
  }

  function acceptMarks(marks) {
    if (!state || !Array.isArray(marks)) return;
    state.marks = marks;
    if (pendingSaveId && marks.some(mark => mark.id === pendingSaveId)) {
      pendingSaveId = null; clearTimeout(saveTimer); notify("Saved to reviews.json");
    }
    renderMarks(); paint();
  }

  function schedulePaint() { clearTimeout(refreshTimer); refreshTimer = setTimeout(paint, 80); }
  function start() {
    refresh();
    if (article) new MutationObserver(schedulePaint).observe(article, { childList: true, subtree: true });
    send("ready", {});
  }
  window.addEventListener("message", event => {
    const message = event.data;
    if (message?.type === "state") acceptMarks(message.marks);
    else if (message?.type === "saveResult" && !message.success) {
      if (pendingSaveId === message.id) pendingSaveId = null;
      notify("Could not save comment. Check the Reading Desk sidebar.");
    } else if (message?.type === "render" && article) {
      article.innerHTML = message.html;
      keepContentInline(); buildContents();
      acceptMarks(message.marks);
      window.dispatchEvent(new Event("vscode.markdown.updateContent"));
    } else if (message?.type === "reveal") revealMark(message.id);
    else if (message?.type === "fragment") scrollToFragment(message.fragment);
  });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
