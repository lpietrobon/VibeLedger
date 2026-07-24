import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";
import { fileURLToPath, URL } from "node:url";

const BASE = "/vibeledger/frontend/";

export default defineConfig({
  base: BASE,
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      injectRegister: "auto",
      includeAssets: ["favicon.svg", "apple-touch-icon-180x180.png"],
      manifest: {
        id: BASE,
        name: "VibeLedger",
        short_name: "VibeLedger",
        description: "Personal finance ledger — accounts, spending, and recurring payments.",
        start_url: BASE,
        scope: BASE,
        display: "standalone",
        orientation: "portrait-primary",
        background_color: "#0f172a",
        theme_color: "#0f172a",
        icons: [
          { src: "pwa-192x192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "pwa-512x512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          { src: "maskable-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // SPA offline: serve the cached app shell for client-side routes.
        navigateFallback: `${BASE}index.html`,
        navigateFallbackAllowlist: [/^\/vibeledger\/frontend\//],
        navigateFallbackDenylist: [/^\/vibeledger\/api\//],
        globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
        runtimeCaching: [
          {
            // Last-known analytics/data so the app opens offline instead of blank.
            urlPattern: ({ url }) => url.pathname.startsWith("/vibeledger/api/"),
            handler: "NetworkFirst",
            options: {
              cacheName: "vibeledger-api",
              networkTimeoutSeconds: 5,
              expiration: { maxEntries: 64, maxAgeSeconds: 60 * 60 * 24 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
});
