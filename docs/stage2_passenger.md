# Stage 2: passenger journeys and live map

## Run

Use Python dependencies from the existing `.venv` and Node 22.12+ (tested with Node 24.19.0). From the BusSure root:

```sh
# Terminal 1
GTFS_SAMPLE=1 .venv/bin/python -B -m uvicorn app.main:app --app-dir backend --port 8000

# Terminal 2
.venv/bin/python -B simulator/multi_bus_simulator.py

# Terminal 3
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. The Vite proxy forwards API and WebSocket traffic to port 8000. There is no periodic full-bus-list poll: the client subscribes, loads `/api/snapshot`, and applies revisioned deltas. Reconnects, revision gaps and resync messages reload the snapshot. Stop each process with Ctrl+C.

When actual GTFS files exist in `datasets/gtfs`, they take precedence over sample fallback. The existing simulator still uses its explicitly configured SAMPLE feed; configure actual route/trip IDs in its JSON if you want simulated vehicles on a supplied real feed. Its positions always retain `SIMULATOR` source.

## Try the passenger flow

1. Click **Use my current location** and grant permission. The blue marker shows your location, with an accuracy circle. The button obtains a fresh browser fix; no location is sent to the bus-ingestion API.
2. Nearby stops show backend Haversine distance and estimated walking minutes. Choose a walking radius. No nearby stops is a valid result when your actual location is outside the loaded dataset.
3. Type part of a destination stop name, then choose a GTFS suggestion. Matching is case-insensitive. Unknown destinations produce an explicit message, never invented results.
4. Direct route cards show boarding/alighting stops and individual eligible buses. Select a card or stop to focus the map. Popups show route/trip IDs, current/next stop, source, status and last fix.
5. Bus markers move via WebSocket; grey markers retain stale positions. Stale/unknown-progress/wrong-direction/passed-boarding buses do not appear as eligible choices. A lost connection hides live availability until resync.
6. Network events appear as orange map markers and a notice strip, and disappear on clear/expiry. No event delay is estimated.

If using fictional data, the app prominently shows **SAMPLE DATA**. For a demonstration away from the fictional coordinates, open **Try a sample journey**, choose **SAMPLE Central**, then **Use SAMPLE origin**. It is labelled **not device GPS**. With a **500 m** radius, search **SAMPLE East** for one route with multiple buses or **SAMPLE North** for two routes. Restart the simulator if its buses have already passed the chosen boarding stop; this is intentional eligibility behavior. The browser test fixture uses slower buses only to keep a stable automated test window.

Preferences are collected but no ranking is applied. Faster/less-crowd selection displays **Prediction model not connected yet**. Fewer transfers explains that only direct routes are currently searched. `predicted_eta`, `predicted_delay`, `predicted_crowd`, and `reliability_score` remain null.

## Backend additions

```sh
curl -sG http://localhost:8000/api/stops/search --data-urlencode 'q=cent'
curl -s http://localhost:8000/api/transit/catalog
curl -sG http://localhost:8000/api/journeys/options \
  --data-urlencode 'latitude=13' --data-urlencode 'longitude=80.005' \
  --data-urlencode 'destination=SAMPLE_E' --data-urlencode 'radius=500'
```

`destination` is the exact stop ID selected from search suggestions. The response includes data provenance, route/boarding/alighting information, backend walking estimates, active buses and valid trip-segment indexes. Each bus must match a valid trip segment, have known upstream progression and a fresh fix. A bus whose current index equals boarding must still be within the configured stop radius. Conditional pickup/drop-off and prohibited boarding/alighting are not offered as ordinary direct journeys.

The browser applies the same eligibility rules to new bus deltas, using the GTFS segment indexes returned by the planner. It does not request a new journey for every GPS fix. Sorting is deterministic walking proximity/route ID and bus ID, not an ETA/crowd recommendation. Route cards may show different boarding choices for the same route.

## Phone passenger testing with trusted HTTPS

Reuse the root README's mkcert setup and certificate files, including trusting the CA on the phone and issuing a certificate for the Mac's current Wi-Fi IP. Keep FastAPI on loopback HTTP; the browser reaches it through the frontend's same-origin TLS proxy:

```sh
# Backend, from the project root
GTFS_SAMPLE=1 .venv/bin/python -B -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000

# Frontend, in frontend/
BUSSURE_HTTPS=1 npm run dev -- --host 0.0.0.0
```

Open `https://YOUR_MAC_WIFI_IP:5173` on the phone. The frontend loads `../.certs/local.pem` and `../.certs/local-key.pem`. The certificate must be trusted without bypassing browser security. Use a trusted local Wi-Fi network; these are unauthenticated development servers. Geolocation on plain HTTP to a LAN address is not supported. Passenger HTTPS on 5173 is separate from the bus-device page's optional TLS setup on 8000.

Allow location → verify blue marker/accuracy and nearby stops → select a destination → watch individual bus markers/cards → create a sample network event using the networking README commands → verify the marker appears/clears. Actual phone GPS validation remains a physical-device task.

## Verification

```sh
# Project root: regression + journey tests
.venv/bin/python -B -m unittest discover -s backend/tests -v
node scripts/test_phone_page.js

# frontend/
npm test
npm run build
```

Browser tests use an installed Google Chrome, Playwright, synthetic geolocation, real API/WebSocket traffic and the existing Python simulator. Start fresh test servers in separate terminals:

```sh
# Project root
GTFS_SAMPLE=1 BUS_STALE_SECONDS=5 .venv/bin/python -B -m uvicorn app.main:app --app-dir backend --port 8012

# frontend/
BUSSURE_BACKEND=http://127.0.0.1:8012 npm run dev -- --port 5174

# Another terminal in frontend/
npm run test:e2e
```

The test itself starts/stops the simulator with `frontend/tests/fixtures/simulator.json`. Do not also run another simulator on the test backend. Tests check desktop/mobile layout, granted and denied GPS paths, nearby stops, unknown and partial destinations, one/multiple routes, two same-route buses, marker movement, stale handling, offline/reconnect/resync, event create/clear, source labels, absent predictions and no passenger GPS uploads. Test-created state lasts until the test backend restarts. Screenshots and failure traces are under `frontend/test-results/` (ignored by Git).

## Limits and provenance

- GTFS route connectivity is static. Calendar dates/times, transfers, reservations and service availability are not evaluated. A valid route is not a promise of service today.
- No real Chennai GTFS has been supplied; testing uses the existing fictional fixture. No Tamil Nadu route numbers were invented.
- GPS stop-radius matching can miss stops with sparse fixes and cannot reliably disambiguate every loop. Unknown progress is excluded rather than guessed. No road-shape line is invented on the map.
- Walking distance is straight-line. No ETA, delay, crowd, reliability score or final AI recommendation exists.
- Map tiles and optional web fonts require internet. A tile error shows a warning while GPS markers still work. The map uses visible OpenStreetMap attribution and standard browser caching, with no bulk tile download. See the [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/) and [React-Leaflet documentation](https://react-leaflet.js.org/docs/start-installation/).
- The existing backend remains single-process/in-memory. No authentication, deployment, database, ML or routing engine was added.
