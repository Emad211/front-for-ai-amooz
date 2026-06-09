import type { NextConfig } from "next";

const backendUrl =
  process.env.NEXT_PUBLIC_API_URL ||
  process.env.BACKEND_URL ||
  "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",

  // Django/DRF URLs end in a slash and APPEND_SLASH cannot redirect POSTs with a
  // body (it raises RuntimeError -> 500). By default Next issues a 308 that strips
  // the trailing slash before the /api rewrite, breaking every POST/PUT/PATCH/DELETE
  // proxied to the backend. Skip that redirect so "/api/foo/" reaches Django intact.
  skipTrailingSlashRedirect: true,

  typescript: {
    // Enforce type-safety at build time (the codebase is now type-clean).
    // Emergency escape hatch only: IGNORE_BUILD_ERRORS=true.
    ignoreBuildErrors: process.env.IGNORE_BUILD_ERRORS === "true",
  },

  eslint: {
    // ESLint flat-config is not wired up yet, so keep it out of the build gate
    // for now (tracked separately). Type-checking above is the real gate.
    ignoreDuringBuilds: true,
  },

  async rewrites() {
    // Capture the remainder with (.*) instead of :path* so the trailing slash is
    // preserved verbatim — :path* drops it, which (combined with Django's
    // APPEND_SLASH) breaks proxied POSTs. Paired with skipTrailingSlashRedirect.
    return [
      {
        source: "/api/:path(.*)",
        destination: `${backendUrl}/api/:path`,
      },
    ];
  },

  images: {
    remotePatterns: [
      {
        protocol: "http",
        hostname: "localhost",
        port: "8000",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "aiamoooz.darkube.ir",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "aiamoooz.darkube.app",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "placehold.co",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "images.unsplash.com",
        pathname: "/**",
      },
      {
        protocol: "https",
        hostname: "picsum.photos",
        pathname: "/**",
      },
    ],
  },
};

export default nextConfig;
