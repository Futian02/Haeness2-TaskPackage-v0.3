/// <reference path="./vite-node-shims.d.ts" />
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { createHash } from "node:crypto";
import { readFileSync, readdirSync } from "node:fs";
import { join, relative } from "node:path";

const frontendRoot = process.cwd();
function frontendSourceFingerprint(): string {
  const files: string[] = [];
  const visit = (directory: string) => {
    for (const entry of readdirSync(directory, { withFileTypes: true })) {
      const absolute = join(directory, entry.name);
      if (entry.isDirectory()) visit(absolute);
      else if (/\.(tsx?|css|html)$/.test(entry.name)) files.push(absolute);
    }
  };
  visit(join(frontendRoot, "src"));
  files.push(join(frontendRoot, "package.json"), join(frontendRoot, "vite.config.ts"), join(frontendRoot, "index.html"));
  const hash = createHash("sha256");
  for (const file of files.sort()) {
    hash.update(relative(frontendRoot, file).replaceAll("\\", "/"));
    hash.update("\0");
    hash.update(readFileSync(file));
    hash.update("\0");
  }
  return hash.digest("hex");
}
const frontendBuildFingerprint = frontendSourceFingerprint();

export default defineConfig({
  define: { __AETHER_FRONTEND_BUILD_FINGERPRINT__: JSON.stringify(frontendBuildFingerprint) },
  plugins: [react(), tailwindcss(), {
    name: "aetheris-runtime-contract-meta",
    transformIndexHtml(html) {
      const tags = `<meta name="aetheris-contract-version" content="aetheris-r2.0.0" />\n    <meta name="aetheris-build-fingerprint" content="${frontendBuildFingerprint}" />`;
      return html.replace("</head>", `    ${tags}\n  </head>`);
    },
  }],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: { "/api": { target: process.env.VITE_API_TARGET || "http://127.0.0.1:8000", changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    restoreMocks: true,
  },
});
