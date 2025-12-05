/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  eslint: {
    // Disable ESLint during builds to avoid Docker build failures
    ignoreDuringBuilds: true,
  },
  typescript: {
    // Don't fail build on TypeScript errors (but we should fix them)
    ignoreBuildErrors: false,
  },
};

module.exports = nextConfig;
