/** @type {import('next').NextConfig} */
const path = require('path');

// Use empty string for local dev (NEXT_PUBLIC_BASE_PATH=""), otherwise default to production path
const basePath = process.env.NEXT_PUBLIC_BASE_PATH !== undefined
  ? process.env.NEXT_PUBLIC_BASE_PATH
  : "/us/working-parents-tax-relief-act";

const nextConfig = {
  ...(basePath ? { basePath } : {}),
  output: "standalone",
  // Set the output file tracing root to this project's frontend directory
  // to avoid issues with lockfiles in parent directories
  outputFileTracingRoot: path.join(__dirname),
  // Allow external images from policyengine.org for optimization
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'policyengine.org',
        pathname: '/assets/**',
      },
    ],
  },
  // Compress responses for better performance
  compress: true,
  // Enable powered-by header removal for security
  poweredByHeader: false,
  // SEO-friendly headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-Frame-Options',
            value: 'SAMEORIGIN',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
