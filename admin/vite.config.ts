import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5174,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  resolve: {
    alias: { "@shared": path.resolve(__dirname, "../shared") },
  },
});
