// The browser only ever talks to this site. /api is forwarded to FastAPI, so the login cookie stays
// first-party and no CORS setup is needed, locally or deployed.
export default {
  rewrites() {
    return [{ source: "/api/:path*", destination: `${process.env.API_URL || "http://localhost:8000"}/:path*` }];
  },
};
