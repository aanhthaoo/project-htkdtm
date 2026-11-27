import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Trong Docker, VITE_API_PROXY=http://backend:8000; chạy ngoài Docker dùng localhost:8000
const apiTarget = process.env.VITE_API_PROXY || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.js"],
    globals: true,
  },
});
