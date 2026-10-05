import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV === "development";

// Everything the page loads comes from this origin; the browser only calls the
// same-origin proxy under /api/agent. Next.js needs inline scripts for hydration, and
// React needs eval in development only.
const contentSecurityPolicy = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${isDev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const nextConfig: NextConfig = {
  // The repository root holds the Python backend; keep Next.js scoped to this folder.
  turbopack: { root: process.cwd() },
  experimental: {
    // Next 16.3 keeps a Turbopack build cache in .next/cache, which Vercel restores between
    // deployments. On 2026-10-05 it served a stale globals.css to production (every rule
    // added since the cache was written was missing). Build from scratch every time.
    turbopackFileSystemCacheForBuild: false,
  },
  poweredByHeader: false,
  // `next dev` serves its own resources to localhost only; also allow the page on 127.0.0.1.
  allowedDevOrigins: ["127.0.0.1"],
  // One landing page with sections; the short URL points at its glossary section.
  async redirects() {
    return [{ source: "/glosarium", destination: "/#glosarium", permanent: false }];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
