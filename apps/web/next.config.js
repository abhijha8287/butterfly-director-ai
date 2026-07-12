/** @type {import('next').NextConfig} */
const nextConfig = {
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
