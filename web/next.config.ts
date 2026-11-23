import type { NextConfig } from "next"

/**
 * Production: a static export (web/out) that the FastAPI service serves next to /api.
 * Development (`npm run dev`): /api is proxied to the local API on port 8000.
 */
const isDev = process.env.NODE_ENV === "development"

const nextConfig: NextConfig = isDev
  ? {
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${process.env.FINXL_API ?? "http://127.0.0.1:8000"}/api/:path*` }]
      },
    }
  : {
      output: "export",
      trailingSlash: true,
      images: { unoptimized: true },
    }

export default nextConfig
