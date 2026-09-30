/**
 * ThemeToggle.jsx
 *
 * Provides explicit switching between Light, Dark, and System (Auto) color modes.
 * Persists user choice in localStorage and sets data-theme on <html>.
 */

import { useEffect, useState } from "react";

const THEME_KEY = "redactbench_theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem(THEME_KEY) || "auto";
    } catch {
      return "auto";
    }
  });

  useEffect(() => {
    const root = document.documentElement;
    try {
      if (theme === "auto") {
        root.removeAttribute("data-theme");
        localStorage.setItem(THEME_KEY, "auto");
      } else {
        root.setAttribute("data-theme", theme);
        localStorage.setItem(THEME_KEY, theme);
      }
    } catch {
      // localStorage may fail in restricted sandboxes
    }
  }, [theme]);

  return (
    <div className="theme-toggle-group" role="radiogroup" aria-label="Seleziona tema">
      <button
        type="button"
        className={`theme-toggle-btn ${theme === "light" ? "active" : ""}`}
        onClick={() => setTheme("light")}
        title="Tema Chiaro (Light Mode)"
        aria-checked={theme === "light"}
        role="radio"
      >
        <span aria-hidden="true">☀️</span>
        <span className="theme-toggle-label">Chiaro</span>
      </button>

      <button
        type="button"
        className={`theme-toggle-btn ${theme === "dark" ? "active" : ""}`}
        onClick={() => setTheme("dark")}
        title="Tema Scuro (Dark Mode)"
        aria-checked={theme === "dark"}
        role="radio"
      >
        <span aria-hidden="true">🌙</span>
        <span className="theme-toggle-label">Scuro</span>
      </button>

      <button
        type="button"
        className={`theme-toggle-btn ${theme === "auto" ? "active" : ""}`}
        onClick={() => setTheme("auto")}
        title="Segui impostazioni di sistema (Auto)"
        aria-checked={theme === "auto"}
        role="radio"
      >
        <span aria-hidden="true">💻</span>
        <span className="theme-toggle-label">Auto</span>
      </button>
    </div>
  );
}

export default ThemeToggle;
