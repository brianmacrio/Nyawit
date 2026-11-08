import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Saat pengembangan, permintaan /api diteruskan ke backend FastAPI (port 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  build: { chunkSizeWarningLimit: 900 },
});
