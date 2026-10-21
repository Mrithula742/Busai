# BusSure passenger UI

React + React-Leaflet + Leaflet, built with Vite. Run Node 22.12+ (tested with Node 24.19.0).

```sh
npm ci
npm run dev
```

Open http://localhost:5173. FastAPI should run on port 8000. Vite proxies `/api` and `/ws` to the same backend, so no permissive CORS setting is needed.

To use another backend port:

```sh
BUSSURE_BACKEND=http://127.0.0.1:8012 npm run dev -- --port 5174
```

Build/check:

```sh
npm test
npm run build
npm run preview
```

Browser acceptance tests use installed Google Chrome and isolated test servers, as explained in [the Stage 2 guide](../docs/stage2_passenger.md). Test geolocation is explicitly synthetic. No physical-device claim is made.
