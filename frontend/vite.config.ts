import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Where the dev server forwards /api. Defaults to a backend running on the host;
// docker-compose overrides it with http://api:8000, because inside the compose
// network the backend is another service rather than localhost.
const apiTarget = process.env.VITE_API_PROXY ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Binding to 0.0.0.0 lets the port mapping reach the server from outside
    // the container; it is harmless when running directly on the host.
    host: true,
    // The API stays same-origin in development, so no CORS round-trip and no
    // base-URL configuration in the client.
    proxy: { "/api": { target: apiTarget, changeOrigin: true } },
  },
});
