export type Theme = "dark" | "light";

const KEY = "ohimymind-theme";
const listeners = new Set<(theme: Theme) => void>();

export function readTheme(): Theme {
  try {
    const value = localStorage.getItem(KEY);
    if (value === "light" || value === "dark") return value;
  } catch {
    /* private mode */
  }
  return "dark";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute("data-theme", theme);
  document.documentElement.style.colorScheme = theme;
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* ignore */
  }
  listeners.forEach((fn) => fn(theme));
}

export function onThemeChange(fn: (theme: Theme) => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}
