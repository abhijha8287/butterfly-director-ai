import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Agent endpoints (story-architect, prompt-director, etc.) call an LLM and
  // routinely take 25-35s. Next's rewrite proxy defaults to a 30s timeout
  // (experimental.proxyTimeout), which was killing the connection out from
  // under slower agent calls with ECONNRESET/"socket hang up" before the
  // backend could respond. Raised to 120s to give every agent headroom.
  experimental: {
    proxyTimeout: 120000,
  },
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: '/api/v1/:path*',
          destination: 'http://api:8000/v1/:path*',
        },
      ],
    };
  },
};

export default nextConfig;
