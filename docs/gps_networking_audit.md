# GPS + networking requirement audit

Audit date: 2026-10-03. The existing seven-test foundation was inspected and run before changes. Existing components were extended in place. There is no Git repository in this workspace, so no commit/diff history is available; the change inventory below records this upgrade.

DONE means implemented and covered by automated or actual local-network tests. It does not claim physical GPS hardware verification. MISSING in the initial column means at least part of the new requirement was absent from the first milestone.

| # | Requirement | Initial audit | Final result / evidence |
|---|---|---|---|
| 1 | Complete GPS software flow | DONE core ingestion/state/stream; MISSING events and backend stop progression | DONE: coordinates/IDs/time validated, latest state per bus, named deltas, stale monitor, GTFS stop association, separate passenger queries, event service. Python and live tests. |
| 2 | Real phone sender | DONE watchPosition/start/stop/mobile page; MISSING diagnostics/canonical source/retry coverage | DONE software: permission, lat/lon, accuracy/weak-quality warning, speed/heading, timestamps, count/status; permission/GPS/network errors; bounded retries, no duplicate tracking; REAL_PHONE_GPS. Seven mocked browser scenarios. Physical phone test pending. |
| 3 | Multi-bus simulator | DONE multiple vehicles/routes/speeds/positions/stop movement/config/time; MISSING distinct trips and canonical source | DONE: six buses, three SAMPLE routes, two buses per route, six distinct GTFS trips, canonical SIMULATOR; stop-chain ordering supports next-bus comparison. Live test sees three changing fixes per bus. |
| 4 | Complete live state | DONE most fields; MISSING canonical aliases | DONE: all requested fields including accuracy and last_received_at; old aliases retained. Source coexistence test. |
| 5 | Stale/offline handling | DONE timestamp-based configurable detection | DONE: canonical STALE status, automatic BUS_STATUS_CHANGED, excluded from active lists, retained in snapshot. Old retries cannot freshen a fix. Real timer verified over WebSocket. |
| 6 | Passenger location/nearby stops | DONE Haversine/order/walking speed; MISSING limit/field aliases | DONE: latitude/longitude/radius/limit, coordinates/name/ID/distance/estimated_walking_minutes, nearest first. No bus creation or passenger persistence. |
| 7 | GTFS service methods/indexes | DONE loader/direct-trip lookup; MISSING named methods and complete indexes/selection policy | DONE all six named methods, route-trip/route-stop/stop-route indexes; streamed CSV and compact stop-time rows; supplied real data preferred, samples marked SAMPLE. Fixtures test malformed feeds and direction. No actual Tamil Nadu feed supplied. |
| 8 | Stop progression | DONE simulator progression; MISSING phone backend association | DONE conservative GPS-radius progression along GTFS sequence; weak fixes withheld, unverified stops null, simulator hints checked. Stop progression test. |
| 9 | REST API | DONE five original endpoints; MISSING route detail and /api/health | DONE all seven requested endpoints, plus network-events/snapshot/nearby-routes/approaching; 200/201/404/409/422/503 behavior tested. |
| 10 | WebSocket | DONE bounded incremental stream; MISSING event names and robust resync versioning | DONE all four event types, atomic snapshot, epoch/revision sequencing, slow-client resync signal, reconnecting viewer. Fanout, stale, event, snapshot and stream-client tests. |
| 11 | Network events | MISSING operational APIs/store/hook; schema only existed | DONE full fields/types including OTHER, create/list/clear, validation, scheduled-window matching, automatic expiry, create/clear broadcasts, no-op simulator extension hook. No ML delays/rerouting. |
| 12 | Source transparency | DONE source separation; MISSING exact enum values | DONE canonical REAL_PHONE_GPS/SIMULATOR in responses, legacy values normalized, bus-ID source switching rejected. Tests use explicitly labelled synthetic phone payload fixtures. |
| 13 | Phone HTTPS instructions | DONE local trusted HTTPS instructions | DONE expanded Mac-IP discovery, 0.0.0.0 meaning, certificate trust, exact phone actions, TLS simulator/viewer commands; no browser-security bypass. Instructions not executed on physical phone. |
| 14 | Verification | DONE first-stage tests; MISSING new coverage | DONE dependency check, syntax/import checks, 20 Python tests, seven mocked phone scenarios, real Uvicorn HTTP/WS acceptance run. |
| 15 | Acceptance A–M | First milestone covered part | DONE software acceptance A–M as detailed below; actual phone device and real operator data remain external validation. |

## Acceptance A–M

| Item | Status | Evidence |
|---|---|---|
| A FastAPI runs | DONE | Uvicorn started and shut down cleanly on 127.0.0.1:8011. |
| B Several simulated buses update | DONE | Six buses, three coordinate updates each over real socket. |
| C GET /api/buses returns buses | DONE | Six simulator records, then seven with phone-protocol fixture. |
| D Two buses share a route | DONE | Two each on SAMPLE_R1, SAMPLE_R2, SAMPLE_R3. |
| E WebSocket streams | DONE | Incremental BUS_LOCATION_UPDATED and event messages observed. |
| F Stale handling | DONE | All seven records automatically STALE after five-second test threshold; active list empty. |
| G Nearby GTFS stops | DONE | Distance ordering, limit, walking estimate and live endpoint checked. |
| H Route numbers from data | DONE | SAMPLE-A/B/C read from sample routes.txt; real feed precedence tested. |
| I Phone GPS payload enters state | DONE protocol | Synthetic PHONE_PAYLOAD_TEST with actual phone schema accepted. Physical GPS fix not observed in this environment. |
| J Phone/simulator coexist | DONE protocol | Both canonical sources in same state/store; source collisions rejected. |
| K Events created/broadcast | DONE | ROAD_BLOCK created (201), listed, cleared (200), both broadcasts observed. |
| L Tests pass | DONE | 20 Python tests, seven phone-page scenarios, live network smoke test. |
| M README instructions | DONE | Install/run/curl/WS/phone HTTPS/GTFS/event/test commands updated. |

## Files created

- `backend/app/api/network_events.py`
- `backend/app/services/network_event_service.py`
- `backend/app/services/stop_progression_service.py`
- `backend/tests/test_networking_stage.py`
- `backend/tests/test_stream_client.py`
- `simulator/network_event_hook.py`
- `simulator/routes/sample_gtfs/SAMPLE`
- `scripts/test_phone_page.js`
- `docs/gps_networking_audit.md`

## Files modified

- `backend/app/config.py`, `backend/app/main.py`
- `backend/app/api/stops.py`, `backend/app/api/routes.py`
- `backend/app/schemas/gps.py`, `bus.py`, `stop.py`, `network_event.py`
- `backend/app/services/bus_state_service.py`, `gps_service.py`, `gtfs_service.py`, `nearby_stop_service.py`
- `backend/app/websocket/manager.py`
- `backend/tests/test_foundation.py`
- `simulator/multi_bus_simulator.py`, `simulator/simulator_config.json`
- `simulator/routes/sample_gtfs/routes.txt`, `trips.txt`, `stop_times.txt`
- `gps_device/index.html`
- `scripts/watch_buses.py`, `scripts/smoke_network.py`
- `README.md`, `backend/README.md`

Existing React and ML placeholders are preserved. No models, crowd/ETA predictions, databases, Docker or external messaging infrastructure were added.

## Packages and commands

No new packages were needed. Re-ran `.venv/bin/python -B -m pip install -r backend/requirements.txt`: all requirements already satisfied. Existing direct packages: FastAPI 0.128.8, Uvicorn 0.39.0, Pydantic 2.13.5, websockets 15.0.1, httpx 0.28.1. `pip check` reports no broken requirements. Node tests use only built-in modules; no npm/React install.

Main verification commands run from the project root:

```sh
.venv/bin/python -B -m pip install -r backend/requirements.txt
.venv/bin/python -B -m pip check
.venv/bin/python -B -m unittest discover -s backend/tests -v
node scripts/test_phone_page.js
GTFS_DIR=simulator/routes/sample_gtfs GTFS_SAMPLE=1 BUS_STALE_SECONDS=5 \
  .venv/bin/python -B -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8011
.venv/bin/python -B scripts/smoke_network.py --backend http://127.0.0.1:8011
```

Python files were AST-parsed and backend modules imported with bytecode writes disabled. The smoke test launches `multi_bus_simulator.py --ticks 3 --backend http://127.0.0.1:8011` internally. Local-server/network commands required sandbox escalation and succeeded. Initial sandbox bind/connect failures were environment restrictions, not application failures.

## REST endpoints verified

Requested: POST `/api/buses/location`; GET `/api/buses`, `/api/buses/{bus_id}`, `/api/routes/{route_id}/buses`, `/api/stops/nearby`, `/api/routes/{route_id}`, `/api/health`.

Additional: GET `/api/snapshot`, `/api/routes/nearby`, `/api/routes/connections`, `/api/routes/{route_id}/stops/{stop_id}/approaching`, `/api/trips/{trip_id}/stops`, `/api/stops/{stop_id}/routes`, `/api/network-events`, `/gps-device`; POST `/api/network-events`, `/api/network-events/{event_id}/clear`. Legacy `/health` remains available.

## Known limitations and remaining validation

- No known failing automated tests or outstanding implementation blockers for this scoped stage.
- Physical phone GPS, certificate trust and browser behavior need the documented on-device acceptance steps. Browser test doubles and a phone-shaped payload do not prove real hardware coordinates.
- No Chennai MTC/TNSTC GTFS was supplied. Tests use clearly fictional SAMPLE data and temporary GTFS fixtures. Actual feed compatibility and operator service claims are unverified.
- The service is an unauthenticated, single-process local prototype. State is cleared on restart; stale buses/cleared events have no retention cleanup yet.
- Stop matching uses a configurable radius. Sparse updates can miss stops; loop/repeated-stop occurrences and trip restarts need explicit new trip IDs for reliable phone progression. This is not road map matching.
- Stop-chain ordering estimates remaining distance only; it cannot promise which bus arrives first. Walking uses straight-line distance. No timetable-date filtering, transfers, road routing or ML is performed.
- The disruption hook is intentionally observational: actual slowdown, stopping and diversion behavior is left for a subsequent requested milestone. Event storage and broadcasts work now.
- Browser background/screen-lock suspension can halt GPS. Keep the sender visible and the screen awake.
- Legacy source/field aliases remain accepted, but consumers must adopt canonical output statuses and named WebSocket events.
