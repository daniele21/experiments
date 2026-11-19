import test from "node:test";
import assert from "node:assert/strict";
import { initialTheme, normalizeTheme, setTheme, THEME_STORAGE_KEY } from "./theme.js";

test("dark mode is default, light opt-in is preserved", () => {
  assert.equal(initialTheme({ getItem: () => null }), "dark");
  assert.equal(initialTheme({ getItem: () => "dark" }), "dark");
  assert.equal(initialTheme({ getItem: () => "light" }), "light");
  assert.equal(initialTheme({ getItem: () => "invalid" }), "dark");
  assert.equal(normalizeTheme("auto"), "dark");
});

test("switching themes updates the DOM immediately and persists selection", () => {
  const root = { dataset: {} };
  const values = new Map();
  const storage = {
    getItem: (key) => values.get(key) || null,
    setItem: (key, val) => { values.set(key, val); },
  };
  assert.equal(setTheme("light", root, storage), "light");
  assert.equal(root.dataset.theme, "light");
  assert.equal(values.get(THEME_STORAGE_KEY), "light");
  assert.equal(initialTheme(storage), "light");
  assert.equal(setTheme("dark", root, storage), "dark");
  assert.equal(root.dataset.theme, "dark");
});

test("private browsing or disabled storage never breaks theme updates", () => {
  const root = { dataset: {} };
  const disabled = {
    getItem: () => { throw new Error("blocked"); },
    setItem: () => { throw new Error("blocked"); },
  };
  assert.equal(initialTheme(disabled), "dark");
  assert.doesNotThrow(() => setTheme("light", root, disabled));
  assert.equal(root.dataset.theme, "light");
});
