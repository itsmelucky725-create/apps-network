"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");
const script = fs.readFileSync(path.join(__dirname, "../assets/language.js"), "utf8");

test("selector enhances the fallback and navigates to the exact chosen locale", () => {
  const handlers = {};
  const control = { hidden: true };
  const links = { hidden: false };
  const select = { value: "../ja/", addEventListener: (event, fn) => { handlers[event] = fn; } };
  const elements = { "language-control": control, lang: select, "language-links": links };
  let destination;
  vm.runInNewContext(script, {
    document: { getElementById: (id) => elements[id] },
    window: { location: { assign: (url) => { destination = url; } } }
  });
  assert.equal(control.hidden, false);
  assert.equal(links.hidden, true);
  handlers.change();
  assert.equal(destination, "../ja/");
  select.value = "./fr/";
  handlers.change();
  assert.equal(destination, "./fr/");
});

test("a missing control leaves the ordinary language links usable", () => {
  assert.doesNotThrow(() => vm.runInNewContext(script, {
    document: { getElementById: () => null }
  }));
});
