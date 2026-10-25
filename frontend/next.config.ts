import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emits .next/standalone with only the traced files; the Dockerfile copies
  // that instead of node_modules.
  output: "standalone",
};

export default nextConfig;
