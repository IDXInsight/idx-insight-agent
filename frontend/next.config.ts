import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The repository root holds the Python backend; keep Next.js scoped to this folder.
  turbopack: { root: process.cwd() },
};

export default nextConfig;
