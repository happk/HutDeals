import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// GitHub Pages 專案頁部署在 /HutDeals/ 子路徑
export default defineConfig({
  base: "/HutDeals/",
  plugins: [react(), tailwindcss()],
  test: {
    environment: "jsdom",
  },
});
