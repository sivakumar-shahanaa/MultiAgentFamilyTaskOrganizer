import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev: vite on 5173 proxying /api + /audit to FastAPI on 8010.
// Prod: `npm run build` -> dist/ is mounted by FastAPI at /app (same origin).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/app/",
  server: {
    proxy: {
      "/api": "http://localhost:8010",
    },
  },
});
