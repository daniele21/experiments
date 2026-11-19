/** Imagebench appearance preference. Dark is the default for this workspace. */
export const THEME_STORAGE_KEY = "imagegen-theme";

export function normalizeTheme(value) {
  return value === "light" ? "light" : "dark";
}

export function initialTheme(storage) {
  try {
    return normalizeTheme(storage?.getItem(THEME_STORAGE_KEY));
  } catch {
    return "dark";
  }
}

export function setTheme(theme, root, storage) {
  const normalized = normalizeTheme(theme);
  root.dataset.theme = normalized;
  try { storage?.setItem(THEME_STORAGE_KEY, normalized); } catch {
    // Storage may be disabled: switching themes must still work in this tab.
  }
  return normalized;
}
