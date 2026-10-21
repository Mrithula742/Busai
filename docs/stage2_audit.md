# Stage 2 implementation and verification audit

Date: 2026-10-03. The attached Stage 2 specification was read in full. Existing files were inspected and all 20 prior backend tests passed before changes. No actual GTFS files were present in `datasets/gtfs/`. The existing GPS/networking architecture and simulator were retained.

## DONE / MISSING audit

| Requirement | Before | After / evidence |
|---|---|---|
| 1 React frontend | MISSING: empty placeholders | DONE: React/Leaflet/Vite page, optional preferences, explicit prediction-unavailable notices; production build and browser tests pass. |
| 2 Passenger current location | MISSING browser passenger flow | DONE: browser geolocation, permission/error/accuracy display, separate blue marker; no bus-ingestion upload. Granted/denied browser paths tested using synthetic browser location. Physical GPS remains unverified. |
| 3 Live map | MISSING | DONE: OSM tiles, passenger/stops/buses/stale/events, selected boarding/destination; initial snapshot plus incremental WebSocket. Screenshots inspected. |
| 4 Bus markers | MISSING | DONE: route label from catalog, route/trip IDs, current/next stop, source, status/time in popups; simulator/stale styling. Marker movement/source title checked in Chrome. |
| 5 Nearby stops | DONE backend; MISSING UI | DONE UI calls existing API and displays backend distance/walking estimate, nearest first. Sample Central is nearest in browser fixture. |
| 6 Destination search | MISSING | DONE partial/case-insensitive GTFS suggestions, selectable IDs, explicit unknown-destination message. No LLM or external geocoder. |
| 7 Journey resolution | MISSING | DONE service/schema/API using nearby origins and directed trip segments, regular pickup/drop-off, actual state-store buses. |
| 8 Multiple routes | MISSING UI | DONE two direct routes from SAMPLE Central to SAMPLE North; backend and browser tests verify. |
| 9 Same-route multiple buses | DONE store; MISSING passenger comparison | DONE separate BUS_001 and BUS_002 cards on SAMPLE-A; no better/best ranking. |
| 10 Relevant approaching buses | Partial distance-ordering foundation | DONE journey-specific filtering by bus's own trip and stop occurrence. Wrong direction, stale, unknown progression and passed boarding are excluded. At-stop vehicles require proximity. Backend/frontend tests cover. |
| 11 Network events on map | DONE backend; MISSING UI | DONE marker + notice strip, severity/route/description, time-window filtering, immediate create/clear delta handling; real browser/API test passes. |
| 12 Component structure | Empty scaffold | DONE requested modular components, hooks and services; unrelated placeholders preserved. |
| 13 Journey endpoint/schema | MISSING | DONE GET /api/journeys/options with boarding/destination/route/walking/buses/segments and four null prediction fields. |
| 14 No fake ML | DONE prior stage | PRESERVED: all prediction fields null; preferences explicitly unapplied; no ETA/delay/crowd/reliability algorithm. |
| 15 Real GTFS precedence | DONE loader | PRESERVED: existing selection policy; sample banner and explicit simulated origin. No replacement of actual feed. Only SAMPLE feed available during tests. |
| 16 Run/test/fix | MISSING Stage 2 coverage | DONE backend/frontend/simulator executed, 26 Python tests, four frontend state tests, two real-Chrome scenarios, seven legacy phone tests, production build and legacy live smoke. |
| 17 Acceptance flow | MISSING passenger UI | DONE in real browser with synthetic geolocation and actual local REST/WebSocket/simulator. Actual physical-device GPS and real-operator feed remain external validation. |

No known missing implementation items for this scoped Stage 2. Physical-device GPS, phone certificate trust and a real Chennai GTFS feed have not been validated here. No DCRNN, ST-GCN, ETA/crowd ML or AI recommendation work was started.

## Files created

- `backend/app/api/journeys.py`
- `backend/app/schemas/journey.py`
- `backend/app/services/journey_service.py`
- `backend/tests/test_journeys.py`
- `frontend/index.html`, `frontend/vite.config.js`, `frontend/package-lock.json`, `frontend/README.md`
- `frontend/src/main.jsx`, `frontend/src/styles.css`
- `frontend/src/hooks/usePassengerLocation.js`
- `frontend/src/components/PassengerMarker.jsx`
- `frontend/src/components/StopMarker.jsx`
- `frontend/src/components/NetworkEventMarker.jsx`
- `frontend/src/components/DestinationSearch.jsx`
- `frontend/src/components/NearbyStops.jsx`
- `frontend/src/components/JourneyOptionCard.jsx`
- `frontend/src/components/BusOptionCard.jsx`
- `frontend/src/services/journey.js`
- `frontend/playwright.config.js`
- `frontend/tests/state.test.js`
- `frontend/tests/browser/passenger.spec.js`
- `frontend/tests/fixtures/simulator.json`
- `docs/stage2_passenger.md`, `docs/stage2_audit.md`

Generated artifacts: `frontend/dist/`, ignored `frontend/test-results/passenger-desktop.png` and `passenger-mobile.png`. `node_modules` and build/test output are ignored. No generated artifacts are needed for source checkout beyond the lockfile.

## Files modified

- `backend/app/main.py`: initialize JourneyService and register additional router; existing APIs/lifespan/store/socket preserved.
- `frontend/package.json`: activate the existing empty frontend scaffold.
- `frontend/src/App.jsx`, `frontend/src/pages/Home.jsx`
- `frontend/src/components/MapView.jsx`, `frontend/src/components/BusMarker.jsx`
- `frontend/src/services/api.js`, `frontend/src/services/websocket.js`
- `.gitignore`: browser-test artifacts.
- `README.md`: Stage 2 startup and links; networking instructions retained.

No changes to the GPS device, bus store, simulator implementation/default configuration, GTFS loader, existing WebSocket backend or stale/network-event services were necessary.

## Packages installed

Direct frontend packages resolved in the lockfile:

| Package | Version |
|---|---|
| react / react-dom | 19.3.0 |
| leaflet | 1.9.4 |
| react-leaflet | 5.0.0 |
| vite | 7.3.6 |
| @vitejs/plugin-react | 5.2.0 |
| @playwright/test | 1.63.0 |

`npm install` added 70 packages; its audit reported zero vulnerabilities. Existing installed Google Chrome was used for browser tests; no additional browser download. No new Python packages. Installed frontend dependencies occupy approximately 69 MB; production output approximately 428 KB. Node version tested: 24.19.0.

## Backend endpoints added

- GET `/api/stops/search?q=...&limit=10`: GTFS-only destination suggestions.
- GET `/api/transit/catalog`: labelled route/stop metadata loaded for map labels.
- GET `/api/journeys/options?latitude=...&longitude=...&destination=STOP_ID&radius=1000&preference=...`: direct GTFS options and eligible active buses. Radius is bounded at 5 km; destination must be a supplied stop ID.

All existing endpoints remain available. No changes to WebSocket wire format were required.

## Commands executed

Representative full verification/startup commands, from the relevant directory:

```sh
# Project root
.venv/bin/python -B -m unittest discover -s backend/tests -v
node scripts/test_phone_page.js
GTFS_DIR=simulator/routes/sample_gtfs GTFS_SAMPLE=1 BUS_STALE_SECONDS=5 \
  .venv/bin/python -B -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8012
.venv/bin/python -B scripts/smoke_network.py --backend http://127.0.0.1:8012

# frontend/
npm install
npm test
npm run build
npm ls --depth=0
BUSSURE_BACKEND=http://127.0.0.1:8012 npm run dev -- --port 5174
npm run test:e2e
```

Browser tests launched the existing simulator with `--config frontend/tests/fixtures/simulator.json --backend http://127.0.0.1:8012`. Backend files were syntax-parsed and new backend modules imported. Browser tests exercised actual page requests through the Vite proxy to FastAPI and actual WebSocket deltas.

## Tests and issues resolved

- 26 Python tests pass: original 20 plus six journey tests, including multiple direct routes, multiple buses, wrong direction, at/past boarding, stale/unknown progression, pickup restrictions, missing GTFS, invalid coordinates, unknown destination and null predictions.
- Four frontend tests pass: snapshot/revision handling; live journey filtering; event time/status filtering; queued deltas and resync controls.
- Two Chrome acceptance scenarios pass: desktop end-to-end flow and mobile denied-permission/sample-origin/layout flow. Desktop includes GPS marker, nearby stops, case-insensitive search, same-route buses, multiple routes, unknown destination, actual marker motion, stale UI, offline/reconnect snapshot and live event create/clear. No passenger location POST was observed.
- Seven original bus-phone page scenarios still pass.
- Vite production build passes. Original live GPS/networking smoke test passes on the extended backend.
- Browser console produced no uncaught application errors in the desktop acceptance scenario. Mobile has no horizontal overflow. Desktop/mobile screenshots were inspected.
- The Vite development proxy logged EPIPE/ECONNRESET when browser tests deliberately disconnected sockets or closed pages. These transport-close warnings did not prevent reconnect/resync; both browser scenarios passed. Test servers and simulator were stopped after verification.
- Initial package installation and local-server bind attempts were blocked by sandbox network restrictions; approved retries succeeded.
- The first desktop browser test failed because its simulator launch resolved one directory above the project. The path was corrected, and both scenarios subsequently passed twice. This was a test harness error, not silently skipped.
- Visual inspection found that a selected stop could obscure the passenger marker; a dedicated upper map pane fixed it. The browser test now asserts the passenger pane's marker is visible. Mobile CSS was corrected to keep all reported nearby stops visible.

## Status and remaining limits

Passenger GPS: browser granted/denied flows verified with Playwright-provided test coordinates; physical location hardware not verified. Bus GPS remains separate and its previous tests pass.

GTFS search: working against the labelled SAMPLE feed. Actual operator data is absent. Calendar dates/times and transfers are not evaluated; direct connectivity is not a claim that a bus runs today.

Live map/WebSocket: moving, stale and source-labelled bus markers work; snapshot/delta/resync/offline recovery and event creation/clearing verified. No recurring full-bus REST poll. Tiles/web fonts need external internet; GPS markers continue if tiles fail.

Bus comparison: separate eligible same-route buses and multiple routes displayed, with backend walking estimates and no prediction/ranking. GTFS stop-radius progress is conservative; sparse/ambiguous/unknown progress can exclude a bus. Buses already at/past the destination or passed boarding are not useful options.

Network events: working live markers and alerts. No invented traffic delay or rerouting.

Remaining validation: physical phone HTTPS/location and actual Chennai GTFS. Existing single-process/in-memory/unauthenticated prototype limitations remain. No known failing tests or outstanding Stage 2 code blockers.
