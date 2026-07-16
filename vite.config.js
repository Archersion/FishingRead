import { defineConfig } from "vite";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  clearScreen: false,
  server: {
    port: 1420,
    strictPort: true,
    host: "127.0.0.1",
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(projectRoot, "index.html"),
        settings: resolve(projectRoot, "settings.html"),
        bookshelf: resolve(projectRoot, "bookshelf.html"),
        toc: resolve(projectRoot, "toc.html"),
      },
    },
  },
});
