import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const repoArtifacts = resolve(__dirname, "../../artifacts");
const registryFile = resolve(__dirname, "../app_registry/data/registry.json");

export default defineConfig({
  base: "./",
  plugins: [
    react(),
    {
      name: "wrg-dashboard-registry-route",
      configureServer(server) {
        server.middlewares.use("/registry/app_registry.json", (_req, res) => {
          try {
            const text = readFileSync(registryFile, "utf8");
            res.setHeader("Content-Type", "application/json; charset=utf-8");
            res.end(text);
          } catch {
            res.statusCode = 404;
            res.setHeader("Content-Type", "application/json; charset=utf-8");
            res.end("{\"error\":\"registry unavailable\"}");
          }
        });
      }
    }
  ],
  publicDir: repoArtifacts,
  server: {
    fs: {
      allow: [resolve(__dirname, "../..")]
    }
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"]
  }
});
