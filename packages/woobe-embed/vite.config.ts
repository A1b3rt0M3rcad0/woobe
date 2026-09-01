import { defineConfig } from "vite";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const root = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  base: "./",
  build: {
    rollupOptions: {
      input: {
        loader: resolve(root, "src/loader.ts"),
        iframe: resolve(root, "iframe.html"),
        preview: resolve(root, "preview.html"),
      },
      output: {
        entryFileNames: (chunk) =>
          chunk.name === "loader" ? "embed.js" : "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]",
      },
    },
  },
});
