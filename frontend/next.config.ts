import type { NextConfig } from "next";

// The /api rewrite runs SERVER-SIDE (inside the Next server / container), so its
// target must be reachable from there. Prefer BACKEND_URL — in Docker it points
// at the backend SERVICE (http://backend:8000) while NEXT_PUBLIC_API_URL stays
// the browser-facing host URL (http://localhost:8000). In prod both are equal;
// in local `npm run dev` only NEXT_PUBLIC_API_URL is set, so it falls back to it.
const backendUrl =
  process.env.BACKEND_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",

  // Django/DRF URLs end in a slash and APPEND_SLASH cannot redirect POSTs with a
  // body (it raises RuntimeError -> 500). By default Next issues a 308 that strips
  // the trailing slash before the /api rewrite, breaking every POST/PUT/PATCH/DELETE
  // proxied to the backend. Skip that redirect so "/api/foo/" reaches Django intact.
  skipTrailingSlashRedirect: true,

  typescript: {
    ignoreBuildErrors: true,
  },

  eslint: {
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
