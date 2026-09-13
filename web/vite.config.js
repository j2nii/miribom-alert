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
});
