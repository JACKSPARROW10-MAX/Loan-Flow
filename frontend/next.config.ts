import type { NextConfig } from "next";

// In production set NEXT_PUBLIC_API_BASE_URL=/api and BACKEND_URL=<gateway URL>.
// Requests then go same-origin through Vercel, so auth cookies stay first-party.
const backendUrl = process.env.BACKEND_URL;

const nextConfig: NextConfig = {
  async rewrites() {
    if (!backendUrl) return [];
    return [{ source: "/api/:path*", destination: `${backendUrl}/:path*` }];
  },
};

export default nextConfig;
