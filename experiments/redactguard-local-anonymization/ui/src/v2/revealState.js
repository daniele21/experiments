/**
 * Explicit local-only reveal controls for PII spans in RedactBench V2.
 * Mask all values by default. A click can reveal exactly one annotation,
 * and the optional "show all" command applies only to annotated spans.
 * No persistence, analytics, storage or server mutations.
 */
export function emptyRevealState() {
  return { all: false, revealed: new Set(), hidden: new Set() };
}

export function revealKey(model, span) {
  return JSON.stringify([model, span.start, span.end, span.pii_type]);
}

export function isRevealed(state, model, span) {
  const key = revealKey(model, span);
  return state.all ? !state.hidden.has(key) : state.revealed.has(key);
}

export function toggleSpanReveal(state, model, span) {
  const key = revealKey(model, span);
  if (state.all) {
    const hidden = new Set(state.hidden);
    if (hidden.has(key)) hidden.delete(key);
    else hidden.add(key);
    return { all: true, revealed: new Set(), hidden };
  }
  const revealed = new Set(state.revealed);
  if (revealed.has(key)) revealed.delete(key);
  else revealed.add(key);
  return { all: false, revealed, hidden: new Set() };
}

export function setAllRevealed(state, all) {
  return all ? { all: true, revealed: new Set(), hidden: new Set() } : emptyRevealState();
}
