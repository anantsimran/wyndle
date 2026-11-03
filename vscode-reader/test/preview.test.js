"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

test("preview defaults to Later and green, and keeps the selected passage for inline comments", () => {
  const handlers = new Map();
  const sent = [];
  let activeElement = null;
  class Element {
    constructor(tag = "div") {
      this.tagName = tag.toUpperCase();
      this.children = [];
      this.attributes = new Map();
      this.classList = { add() {}, remove() {} };
      this.style = { setProperty() {}, removeProperty() {} };
      this.textContent = "";
      this.value = "";
      this.hidden = false;
    }
    append(...children) {
      this.children.push(...children);
      for (const child of children) child.parent = this;
      if (this.tagName === "SELECT" && children.length && !this.value) this.value = children[0].value;
    }
    appendChild(child) { this.append(child); }
    replaceChildren(...children) { this.children = []; this.append(...children); }
    addEventListener(name, handler) {
      const list = this.listeners ||= new Map();
      list.set(name, [...(list.get(name) || []), handler]);
    }
    fire(name) {
      const event = { target: this, preventDefault() {}, stopPropagation() {}, clientX: 100, clientY: 100 };
      for (const handler of this.listeners?.get(name) || []) handler(event);
    }
    setAttribute(name, value) { this.attributes.set(name, value); }
    removeAttribute(name) { this.attributes.delete(name); }
    getAttribute(name) { return this.attributes.get(name); }
    contains(node) { for (let current = node; current; current = current.parent) if (current === this) return true; return false; }
    closest(selector) { if (selector === ".markdown-body" && this === data) return article; return null; }
    querySelector() { return null; }
    querySelectorAll(selector) { return this === article && selector === "h1,h2,h3,h4,h5,h6" ? headings :
      this === tocList && selector === "button" ? this.children.filter(child => child.tagName === "BUTTON") : []; }
    focus() { activeElement = this; }
    find(predicate) {
      if (predicate(this)) return this;
      for (const child of this.children) { const result = child.find?.(predicate); if (result) return result; }
      return null;
    }
  }
  const article = new Element("article");
  article.textContent = "The key sentence";
  const headings = [new Element("h1"), new Element("h2")];
  headings[0].textContent = "Introduction";
  headings[1].textContent = "Second topic";
  headings[0].getBoundingClientRect = () => ({ top: 10 });
  headings[1].getBoundingClientRect = () => ({ top: 500 });
  let jumped = false;
  headings[1].scrollIntoView = () => { jumped = true; };
  const tocSearch = new Element("input");
  const tocList = new Element("nav");
  const commentsPanel = new Element("section");
  commentsPanel.className = "reading-desk-comments";
  let commentsJumped = false;
  commentsPanel.scrollIntoView = () => { commentsJumped = true; };
  const block = new Element("p"); block.parent = article;
  const textNode = { parent: block, parentElement: block, textContent: article.textContent };
  const data = new Element("span");
  data.setAttribute("data-state", JSON.stringify({ source: "file:///guide.md", scheme: "vscode", token: "test", marks: [] }));
  const body = new Element("body");
  const document = {
    body, readyState: "complete",
    get activeElement() { return activeElement; },
    createElement: tag => new Element(tag),
    querySelector: selector => selector === ".markdown-body" ? article :
      selector === ".reading-desk-toc-search" ? tocSearch :
        selector === ".reading-desk-toc-list" ? tocList :
          selector === ".reading-desk-comments" ? commentsPanel : null,
    getElementById: id => id === "reading-desk-data" ? data : null,
    addEventListener: (name, handler) => handlers.set(name, [...(handlers.get(name) || []), handler]),
    createRange: () => ({ selectNodeContents() {}, setStart() {}, setEnd(_node, offset) { this.offset = offset; }, toString() { return article.textContent.slice(0, this.offset); } }),
    createTreeWalker: () => { let first = true; return { nextNode() { if (!first) return null; first = false; return textNode; } }; },
  };
  const range = { startContainer: textNode, endContainer: textNode, startOffset: 4, endOffset: 7,
    toString: () => "key", getBoundingClientRect: () => ({ left: 100, bottom: 100 }) };
  const selection = { isCollapsed: false, rangeCount: 1, getRangeAt: () => range, toString: () => "key" };
  const context = { document, window: { getSelection: () => selection, innerWidth: 900, innerHeight: 700,
    addEventListener() {} }, acquireVsCodeApi: () => ({ postMessage: message => sent.push(message) }),
    Element, MutationObserver: class { observe() {} }, CSS: { highlights: { delete() {} } },
    NodeFilter: { SHOW_TEXT: 4 },
    crypto: { randomUUID: () => "f6ef80c3-9409-49b0-840d-b71558a317dd" },
    URL, setTimeout: () => 1, clearTimeout() {}, console };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "..", "media", "preview.js"), "utf8"), context);

  const toolbar = body.find(element => element.className === "reading-desk-toolbar");
  const later = toolbar.find(element => element.textContent === "↩ Later");
  const review = toolbar.find(element => element.textContent === "✓ Review");
  const highlight = toolbar.find(element => element.textContent === "Highlight");
  const green = toolbar.find(element => element.title === "green mark");
  const red = toolbar.find(element => element.title === "red mark");
  const add = toolbar.find(element => element.textContent === "+ Add mark");
  const commentsButton = toolbar.find(element => element.textContent === "☰ Comments");
  const save = body.find(element => element.className === "reading-desk-save");
  assert.equal(save.tagName, "BUTTON");
  assert.equal(save.href, undefined);
  const dialog = body.find(element => element.className === "reading-desk-dialog");
  assert.deepEqual(tocList.children.map(child => child.textContent), ["Introduction", "Second topic"]);
  tocList.children[1].fire("click");
  assert.equal(jumped, true);
  tocSearch.value = "second"; tocSearch.fire("input");
  assert.deepEqual(tocList.children.map(child => child.textContent), ["Second topic"]);
  assert.equal(later.getAttribute("aria-pressed"), "true");
  assert.equal(green.getAttribute("aria-pressed"), "true");
  assert.equal(add.getAttribute("aria-disabled"), "true");
  assert.equal(body.find(element => element.className === "reading-desk-comments"), null);
  assert.equal(commentsPanel.hidden, false);
  commentsButton.fire("click");
  assert.equal(commentsJumped, true);
  assert.equal(activeElement, commentsPanel.find(element => element.tagName === "INPUT"));

  add.fire("pointerdown"); add.fire("click");
  assert.equal(dialog.hidden, false);
  save.fire("click");
  let payload = sent.find(message => message.type === "create");
  assert.equal(payload.type, "create");
  assert.equal(payload.kind, "later");
  assert.equal(payload.color, "green");
  assert.equal(payload.anchor.quote, "key");
  assert.equal(commentsPanel.hidden, false);
  assert.equal(commentsPanel.find(element => element.className === "reading-desk-card")?.tagName, "SECTION");
  selection.isCollapsed = true;
  document.caretRangeFromPoint = () => ({ startContainer: textNode, startOffset: 5 });
  for (const handler of handlers.get("click") || []) handler({ target: textNode, clientX: 100, clientY: 100, preventDefault() {}, stopPropagation() {} });
  const popover = body.find(element => element.className === "reading-desk-popover");
  assert.equal(popover.hidden, false);
  assert.equal(popover.children[0].children[0].textContent, "Return later");
  selection.isCollapsed = false;

  review.fire("click");
  assert.equal(review.getAttribute("aria-pressed"), "true");
  assert.equal(green.getAttribute("aria-pressed"), "true");
  highlight.fire("click"); red.fire("click");
  assert.equal(red.getAttribute("aria-pressed"), "true");
  assert.equal(green.getAttribute("aria-pressed"), "false");
  add.fire("pointerdown"); add.fire("click");
  save.fire("click");
  payload = sent.filter(message => message.type === "create")[1];
  assert.equal(payload.kind, "highlight");
  assert.equal(payload.color, "red");
  assert.equal(payload.anchor.quote, "key");
});
