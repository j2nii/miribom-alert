import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

// Local stand-in for `vercel dev`, which keeps failing on this machine
// (missing yarn, npm registry fetch errors -- see docs/meeting-notes/UI/).
// Runs the exact same api/*.js handler files Vercel deploys, just adapted
// to Node's built-in http server instead of Vercel's runtime. Pair with the
// Vite proxy in vite.config.js (`/api` -> this server) so `npm run dev`
// alone gives you a fully working app, chat included.
//
// Usage: npm run dev:api   (in a second terminal, alongside `npm run dev`)
const ROOT = import.meta.dirname;

function loadEnvFile(file) {
  if (!fs.existsSync(file)) return;
  for (const line of fs.readFileSync(file, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}

// .env.local last so it can override shared .env values, same precedence
// convention Vercel/Next.js use.
loadEnvFile(path.join(ROOT, ".env"));
loadEnvFile(path.join(ROOT, ".env.local"));

const { default: queryHandler } = await import(pathToFileURL(path.join(ROOT, "api", "query.js")).href);
const { default: briefingHandler } = await import(pathToFileURL(path.join(ROOT, "api", "briefing.js")).href);

const ROUTES = {
  "/api/query": queryHandler,
  "/api/briefing": briefingHandler,
};

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host ?? "localhost"}`);
  const handler = ROUTES[url.pathname];
  if (!handler) {
    res.statusCode = 404;
    res.end("Not found");
    return;
  }

  let body;
  if (req.method === "POST") {
    const chunks = [];
    for await (const chunk of req) chunks.push(chunk);
    const raw = Buffer.concat(chunks).toString("utf8");
    try {
      body = raw ? JSON.parse(raw) : {};
    } catch {
      res.statusCode = 400;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ error: "invalid JSON body" }));
      return;
    }
  }
  req.body = body;

  // Vercel's Node runtime hands api/*.js the *real* http.ServerResponse,
  // just augmented with `.status()`/`.json()` convenience methods -- it's
  // not a replacement object, so raw streaming (writeHead/write/end, used
  // by query.js for token-by-token output) still works. Bolt the same two
  // methods onto the real `res` here instead of building a separate shim,
  // so api/*.js files run completely unmodified either way.
  res.status = function (code) {
    this.statusCode = code;
    return this;
  };
  res.json = function (obj) {
    if (!this.headersSent) this.setHeader("Content-Type", "application/json");
    this.end(JSON.stringify(obj));
  };

  try {
    await handler(req, res);
  } catch (err) {
    if (!res.headersSent) {
      res.statusCode = 500;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ error: String(err?.message ?? err) }));
    } else {
      res.end();
    }
  }
});

const PORT = process.env.DEV_API_PORT || 3001;
server.listen(PORT, () => {
  console.log(`[dev-api] http://localhost:${PORT} (routes: ${Object.keys(ROUTES).join(", ")})`);
  console.log(`[dev-api] UPSTAGE_API_KEY loaded: ${Boolean(process.env.UPSTAGE_API_KEY)}`);
});
