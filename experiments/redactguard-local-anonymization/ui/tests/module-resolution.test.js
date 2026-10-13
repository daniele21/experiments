import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src/v2");

// macOS default APFS is commonly case-insensitive. Vite resolves bare imports
// by extension priority, so Foo.jsx and foo.js can resolve to the WRONG file.
// Linux CI would otherwise silently miss this regression.
test("v2 modules have distinct case-insensitive file stems across JS/JSX", () => {
  const stems = new Map();
  for (const name of readdirSync(root)) {
    if (!/\.(jsx?|tsx?)$/.test(name)) continue;
    const stem = name.replace(/\.(jsx?|tsx?)$/, "").toLowerCase();
    assert.equal(
      stems.get(stem), undefined,
      `Ambiguous v2 import on case-insensitive macOS: ${stems.get(stem)} vs ${name}`,
    );
    stems.set(stem, name);
  }
});

test("capability page imports the actual default-exporting JSX component", () => {
  const page = readFileSync(path.join(root, "CapabilitiesPage.jsx"), "utf8");
  const component = readFileSync(path.join(root, "ModelDatasetMatrixView.jsx"), "utf8");
  assert.match(page, /import CapabilityMatrix from ["']\.\/ModelDatasetMatrixView\.jsx["'];/);
  assert.match(component, /export default function CapabilityMatrix\(/);
  assert.doesNotMatch(page, /import CapabilityMatrix from ["']\.\/capabilityMatrix(?:\.js)?["'];/i);
});
