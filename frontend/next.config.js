/** @type {import('next').NextConfig} */
const nextConfig = {
  async redirects() {
    return [
      {
        source: '/dashboard/certificate',
        destination: '/dashboard/certificates',
        permanent: false,
      },
    ];
  },
};

module.exports = nextConfig;
