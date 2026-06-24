import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// MetaGaAP 2 frontend. During development the React dev server proxies API and
// WebSocket traffic to the FastAPI backend on 127.0.0.1:8000. The production
// build is emitted into the backend package so `python -m metagaap2` can serve
// the UI directly (single local app, no separate web server).
const BACKEND = process.env.METAGAAP_BACKEND ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: BACKEND, changeOrigin: true },
      "/ws": { target: BACKEND, ws: true, changeOrigin: true },
    },
  },
  build: {
    outDir: "../backend/metagaap2/webui",
    emptyOutDir: true,
  },
});
