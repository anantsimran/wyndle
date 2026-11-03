"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { makeAnchor, bestMatch } = require("../anchors");

test("a passage follows nearby edits and duplicate text stays at the intended occurrence", () => {
  const original = "First occurrence. target phrase. Later target phrase again.";
  const at = original.lastIndexOf("target phrase");
  const anchor = makeAnchor(original, at, at + "target phrase".length);
  const edited = "New preface. " + original;
  assert.equal(bestMatch(edited, anchor).start, at + 13);
});

test("removed text stays unlocated", () => {
  const anchor = makeAnchor("One unique passage here", 4, 18);
  assert.equal(bestMatch("One different passage here", anchor), null);
});

test("an identical phrase without its original context does not steal a mark", () => {
  const anchor = makeAnchor("Alpha target omega", 6, 12);
  assert.equal(bestMatch("Beta target gamma", anchor), null);
});
