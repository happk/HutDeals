import { useCallback, useEffect, useState } from "react";

type Theme = "light" | "dark";
const KEY = "hutdeals-theme";

function systemPref(): Theme {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function initial(): Theme {
  try {
    const saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* localStorage 不可用時退回系統偏好 */
  }
  return systemPref();
}

/**
 * 黑暗模式 hook。進場先讀 localStorage 記的使用者選擇，
 * 沒選過則依瀏覽器 prefers-color-scheme；切換寫回 localStorage 並同步 <html class>。
 */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initial);

  useEffect(() => {
    const el = document.documentElement;
    el.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(KEY, theme);
    } catch {
      /* 忽略寫入失敗 */
    }
  }, [theme]);

  const toggle = useCallback(
    () => setTheme((t) => (t === "dark" ? "light" : "dark")),
    [],
  );

  return { theme, toggle };
}
