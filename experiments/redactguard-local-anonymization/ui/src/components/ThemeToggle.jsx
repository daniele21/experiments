/**
 * ThemeToggle.jsx
 *
 * Explicit Light, Dark, and System theme control.
 */

import { useEffect, useState } from "react";
import {
  applyThemePreference,
  readThemePreference,
} from "../theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState(readThemePreference);

  useEffect(() => {
    applyThemePreference(theme);
  }, [theme]);

  return (
    <div className="theme-toggle-group" role="radiogroup" aria-label="Color theme">
      <button
        type="button"
        className={`theme-toggle-btn ${theme === "light" ? "active" : ""}`}
        onClick={() => setTheme("light")}
        title="Light mode"
        aria-checked={theme === "light"}
        role="radio"
      >
        <span aria-hidden="true">☀️</span>
        <span className="theme-toggle-label">Light</span>
      </button>

      <button
        type="button"
        className={`theme-toggle-btn ${theme === "dark" ? "active" : ""}`}
        onClick={() => setTheme("dark")}
        title="Dark mode"
        aria-checked={theme === "dark"}
        role="radio"
      >
        <span aria-hidden="true">🌙</span>
        <span className="theme-toggle-label">Dark</span>
      </button>

      <button
        type="button"
        className={`theme-toggle-btn ${theme === "auto" ? "active" : ""}`}
        onClick={() => setTheme("auto")}
        title="Follow system appearance"
        aria-checked={theme === "auto"}
        role="radio"
      >
        <span aria-hidden="true">◐</span>
        <span className="theme-toggle-label">Auto</span>
      </button>
    </div>
  );
}

export default ThemeToggle;
