import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// data/mock/*.json and data/prod/*.json live at the repo root, one level
// above this project. Serving them via publicDir keeps scripts/gen_mock.py
// output as the single source of truth -- no copy step needed, and the
// mock -> real swap later is just a manifest URL change, not a rebuild.
export default defineConfig({
  plugins: [react()],
  publicDir: path.resolve(__dirname, "../data"),
  server: {
    // Proxies /api/* to dev-server.mjs (`npm run dev:api`, run alongside
    // this) -- a Node stand-in for `vercel dev` that runs the same api/*.js
    // handler files. changeOrigin stays false so the Host header this dev
    // server sees is still Vite's own (e.g. localhost:5173), which is what
    // api/query.js needs to fetch /mock|prod/*.json back from Vite itself.
    proxy: {
      "/api": { target: "http://localhost:3001", changeOrigin: false },
    },
  },
});
