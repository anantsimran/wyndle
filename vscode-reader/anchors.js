"use strict";

// Shared by the webview and the Node tests. Text offsets use the rendered article's
// textContent, so a mark can cross inline Markdown elements without changing the file.
function bestMatch(text, anchor) {
  if (!anchor || !anchor.quote) return null;
  let from = 0;
  let best = null;
  while (true) {
    const at = text.indexOf(anchor.quote, from);
    if (at < 0) break;
    let score = -Math.abs(at - (anchor.position || 0)) / 100;
    const before = text.slice(Math.max(0, at - (anchor.prefix || "").length), at);
    const after = text.slice(at + anchor.quote.length, at + anchor.quote.length + (anchor.suffix || "").length);
    const hasContext = Boolean(anchor.prefix || anchor.suffix);
    const matchedContext = (anchor.prefix && before === anchor.prefix) || (anchor.suffix && after === anchor.suffix);
    if (hasContext && !matchedContext) { from = at + 1; continue; }
    if (before === (anchor.prefix || "")) score += 100;
    if (after === (anchor.suffix || "")) score += 100;
    if (!best || score > best.score) best = { start: at, end: at + anchor.quote.length, score };
    from = at + 1;
  }
  return best;
}

function makeAnchor(text, start, end) {
  return {
    quote: text.slice(start, end),
    prefix: text.slice(Math.max(0, start - 48), start),
    suffix: text.slice(end, end + 48),
    position: start,
  };
}

const api = { bestMatch, makeAnchor };
if (typeof module !== "undefined") module.exports = api;
if (typeof window !== "undefined") window.MarkdownReadingAnchors = api;
