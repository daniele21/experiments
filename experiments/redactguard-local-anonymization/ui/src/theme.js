export const THEME_KEY = "redactbench_theme";
export const THEME_VALUES = new Set(["light", "dark", "auto"]);

export function readThemePreference() {
  try {
    const stored = localStorage.getItem(THEME_KEY);
    return THEME_VALUES.has(stored) ? stored : "auto";
  } catch {
    return "auto";
  }
}

export function applyThemePreference(theme) {
  const normalized = THEME_VALUES.has(theme) ? theme : "auto";
  const root = document.documentElement;

  if (normalized === "auto") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", normalized);
  }

  try {
    localStorage.setItem(THEME_KEY, normalized);
  } catch {
    // Storage can be unavailable in restricted environments.
  }

  return normalized;
}

// Apply the persisted choice before React mounts to avoid a light/dark flash.
export function initializeTheme() {
  return applyThemePreference(readThemePreference());
}
