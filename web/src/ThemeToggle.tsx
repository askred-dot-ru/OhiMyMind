import { useState } from "react";
import { applyTheme, readTheme, type Theme } from "./theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(() => readTheme());

  function toggle() {
    const next: Theme = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }

  return (
    <button type="button" className="theme-toggle" onClick={toggle} title={theme === "dark" ? "Светлая тема" : "Тёмная тема"}>
      {theme === "dark" ? "Светлая" : "Тёмная"}
    </button>
  );
}
