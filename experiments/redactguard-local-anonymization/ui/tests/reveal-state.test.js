import test from "node:test";
import assert from "node:assert/strict";
import {
  emptyRevealState, isRevealed, toggleSpanReveal,
  setAllRevealed,
} from "../src/v2/revealState.js";

const pii = {start: 12, end: 25, pii_type: "private_email", value: "user@work.test"};
const other = {start: 12, end: 25, pii_type: "private_person", value: "Different type"};
test("PII is masked initially; click reveals and second click hides", () => {
  const start = emptyRevealState();
  assert.equal(isRevealed(start, "qwen4", pii), false);
  const shown = toggleSpanReveal(start, "qwen4", pii);
  assert.equal(isRevealed(shown, "qwen4", pii), true);
  assert.equal(isRevealed(shown, "qwen9", pii), false, "other model stays masked");
  assert.equal(isRevealed(shown, "qwen4", other), false, "other span stays masked");
  const hidden = toggleSpanReveal(shown, "qwen4", pii);
  assert.equal(isRevealed(hidden, "qwen4", pii), false);
  assert.equal(isRevealed(start, "qwen4", pii), false, "state immutable");
});
test("show all is explicit, individual overrides work and hide all resets", () => {
  const all = setAllRevealed(emptyRevealState(), true);
  assert.equal(isRevealed(all, "qwen4", pii), true);
  assert.equal(isRevealed(all, "qwen9", pii), true);
  const oneHidden = toggleSpanReveal(all, "qwen9", pii);
  assert.equal(isRevealed(oneHidden, "qwen9", pii), false);
  assert.equal(isRevealed(oneHidden, "qwen4", pii), true);
  const showAgain = toggleSpanReveal(oneHidden, "qwen9", pii);
  assert.equal(isRevealed(showAgain, "qwen9", pii), true);
  const masked = setAllRevealed(showAgain, false);
  assert.equal(isRevealed(masked, "qwen9", pii), false);
  assert.equal(isRevealed(masked, "qwen4", pii), false);
  assert.equal(masked.revealed.size, 0);
});
test("new run, document or model state can be reset without retaining PII", () => {
  const old = toggleSpanReveal(emptyRevealState(), "qwen4", pii);
  const reset = emptyRevealState();
  assert.equal(isRevealed(old, "qwen4", pii), true);
  assert.equal(isRevealed(reset, "qwen4", pii), false);
});
