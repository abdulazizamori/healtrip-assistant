import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // STATIC_EXPORT=1 (single-service image, see /Dockerfile): plain HTML/JS in out/, served by the API.
  // Otherwise a standalone Node server (docker compose).
  output: process.env.STATIC_EXPORT ? "export" : "standalone",
  poweredByHeader: false,
};

export default nextConfig;
