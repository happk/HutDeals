import { useCallback, useState } from "react";

const STORAGE_KEY = "hutdealsFavorites";

function load(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return new Set(JSON.parse(raw) as string[]);
  } catch {
    // 壞掉的 JSON 視同無收藏
  }
  return new Set();
}

function save(favorites: Set<string>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...favorites]));
}

/** 收藏清單(localStorage 持久化);回傳 [集合, 切換函式]。 */
export function useFavorites(): [Set<string>, (key: string) => void] {
  const [favorites, setFavorites] = useState<Set<string>>(load);

  const toggle = useCallback((key: string) => {
    setFavorites((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      save(next);
      return next;
    });
  }, []);

  return [favorites, toggle];
}
