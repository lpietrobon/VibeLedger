import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import { extname, join, normalize, resolve } from "node:path";
import { request } from "node:http";
import { createServer } from "node:http";

// This process is an authenticated application edge, not a network boundary.
// Keep it on loopback and expose it only through Tailscale Serve.
const host = process.env.FRONTEND_HOST ?? "127.0.0.1";
const port = Number(process.env.PORT ?? process.env.FRONTEND_PORT ?? 5173);
const rootDir = resolve(new URL(".", import.meta.url).pathname);
const distDir = join(rootDir, "dist");
const apiTarget = process.env.VIBELEDGER_API_TARGET ?? "http://127.0.0.1:8000";
const apiToken = process.env.VIBELEDGER_API_TOKEN ?? readDotEnv("VIBELEDGER_API_TOKEN");

const contentTypes = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
};

createServer((req, res) => {
  const url = new URL(req.url ?? "/", `http://${req.headers.host ?? host}`);

  if (url.pathname.startsWith("/vibeledger/api/")) {
    proxyApi(req, res, url);
    return;
  }

  if (
    url.pathname === "/vibeledger/health" ||
    url.pathname.startsWith("/vibeledger/connect/")
  ) {
    proxyBackend(req, res, url);
    return;
  }

  if (url.pathname === "/vibeledger/frontend" || url.pathname.startsWith("/vibeledger/frontend/")) {
    serveFrontend(url.pathname, res);
    return;
  }

  if (url.pathname === "/vibeledger" || url.pathname === "/vibeledger/") {
    res.writeHead(302, { Location: "/vibeledger/frontend/" });
    res.end();
    return;
  }

  res.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
  res.end("Not found");
}).listen(port, host, () => {
  console.log(`VibeLedger frontend listening on http://${host}:${port}/vibeledger/frontend/`);
});

function proxyApi(req, res, url) {
  const upstreamPath = url.pathname.replace(/^\/vibeledger\/api/, "") + url.search;
  proxyRequest(req, res, upstreamPath, true);
}

function proxyBackend(req, res, url) {
  const upstreamPath = url.pathname.replace(/^\/vibeledger/, "") + url.search;
  proxyRequest(req, res, upstreamPath, false);
}

function proxyRequest(req, res, upstreamPath, injectApiToken) {
  const target = new URL(upstreamPath, apiTarget);
  const headers = { ...req.headers, host: target.host };
  if (injectApiToken && apiToken) headers.authorization = `Bearer ${apiToken}`;
  delete headers.connection;

  const upstream = request(
    target,
    {
      method: req.method,
      headers,
    },
    (upstreamRes) => {
      res.writeHead(upstreamRes.statusCode ?? 502, upstreamRes.headers);
      upstreamRes.pipe(res);
    },
  );

  upstream.on("error", (error) => {
    res.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    res.end(JSON.stringify({ detail: `api proxy failed: ${error.message}` }));
  });

  req.pipe(upstream);
}

function serveFrontend(pathname, res) {
  const relative = pathname.replace(/^\/vibeledger\/frontend\/?/, "") || "index.html";
  const candidate = normalize(join(distDir, relative));
  const file = candidate.startsWith(distDir) && existsSync(candidate) && statSync(candidate).isFile()
    ? candidate
    : join(distDir, "index.html");

  res.writeHead(200, {
    "Content-Type": contentTypes[extname(file)] ?? "application/octet-stream",
    "Cache-Control": file.endsWith("index.html") ? "no-cache" : "public, max-age=31536000, immutable",
  });
  createReadStream(file).pipe(res);
}

function readDotEnv(name) {
  const envPath = resolve(rootDir, "..", ".env");
  if (!existsSync(envPath)) return undefined;
  const line = readFileSync(envPath, "utf8")
    .split(/\r?\n/)
    .find((entry) => entry.startsWith(`${name}=`));
  if (!line) return undefined;
  return line.slice(name.length + 1).replace(/^['"]|['"]$/g, "");
}
