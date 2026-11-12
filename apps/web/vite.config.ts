import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig(({ mode }) => ({
  root: fileURLToPath(new URL(".", import.meta.url)),
  publicDir: mode === "demo" ? "public-demo" : "public",
  plugins: [react()],
  server: { proxy: mode === "demo" ? undefined : { "/api": "http://127.0.0.1:8000" } },
  build: { outDir: mode === "demo" ? "dist-demo" : "dist", emptyOutDir: true },
}));
