# BusSure integrated synthetic AI system

BusSure now connects the original GPS/WebSocket/GTFS foundation to separately trained seven-stop ST-GCN crowd and 18-segment DCRNN travel forecasts, bounded transfer planning, disruption scenarios and explainable reliability. All Chennai services and model histories are generated. The original baseline and fictional presentation planners remain available in collapsed sections; historical Salvador inference stays separate.

## Portfolio showcase extension

The same startup now includes **Digital Twin**, **Smart Journey Comparison**, **What-If Studio**, **Rule-Based Journey Assistant**, **Model Performance Dashboard**, and **Smart Boarding Alerts**. No retraining is needed. See [the showcase walkthrough](showcase.md) and [verified implementation report](showcase_report.md). The new checkpoint ignore exceptions allow both small synthetic `.pt` files to be included in a future repository checkout.

## Start from the project root

Use the existing `.venv`, or create it and install dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m pip install -r ml/synthetic/requirements.txt
```

The generated dataset and trained synthetic artifacts are already included locally. To reproduce them:

```sh
.venv/bin/python scripts/generate_synthetic.py
.venv/bin/python -B -m ml.synthetic.train --epochs 18
```

Terminal 1:

```sh
GTFS_DIR=datasets/synthetic_chennai .venv/bin/python -B -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Terminal 2:

```sh
.venv/bin/python -B simulator/multi_bus_simulator.py --config datasets/synthetic_chennai/simulator.json
```

Terminal 3:

```sh
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173 → Start journey → AI Journey. Search Madipakkam → Chennai Central for direct and transfer alternatives, or Madipakkam → Kanchipuram for one-transfer journeys. Choose fastest, lowest crowd, fewer transfers or most reliable; select an option, then Track in My Journey. Results refresh every 10 seconds while the tab is visible, preserving the selected option when it remains feasible. If the selected option becomes unavailable, a notice asks you to review its replacement. Model Insights separates synthetic training from historical experiments.

Allow device location explicitly to plan from nearby boarding stops; the integrated form accepts only a device fix for that mode. Walking is straight-line distance at 1.4 m/s, not turn-by-turn road guidance. Live Map displays source-labelled simulator/device vehicles, stop markers and events. The selected AI itinerary has its own map with the same GPS stream and generated route shapes. Forecasts use saved synthetic histories, not inferred real-time crowd measurements.

Expand Synthetic disruption controls to activate/clear congestion, roadblock, breakdown, temporary delay, rainfall or crowd surge scenarios. Controls use current server time, so choose a departure near now whose segment traversal overlaps the event window to observe an impact. Simulator speeds and accumulated synthetic scenario delay respond to active scopes; roadblocks stop affected movement. The simulator loops independent of the timetable and is labelled as continuous simulation, not scheduled trip adherence.

## Physical phone GPS

The existing sender remains at http://localhost:8000/gps-device. On a physical phone use trusted HTTPS and the same backend; follow the root README's mkcert/network setup. Choose a valid bus ID, route and trip, press Start Tracking and explicitly allow location. Keep the page foregrounded. Fix timestamps, source labels, sequence progression, stale detection and WebSocket broadcasts are preserved. Passenger location is never uploaded as a bus. Physical hardware and mobile permission behaviour require a separate device test; automated browser/GPS doubles do not establish that result.

## Configuration

| Setting | Purpose |
|---|---|
| `GTFS_DIR=datasets/synthetic_chennai` | Required active network for the integrated AI planner |
| `BUS_STALE_SECONDS=45` | Default GPS freshness threshold |
| `BUSSURE_BACKEND=http://127.0.0.1:8000` | Vite proxy target; set before `npm run dev` for another backend |
| `BUSSURE_DISABLE_MODELS=1` | Force a visibly labelled baseline fallback |
| `GTFS_SAMPLE=1` | Original sample fallback only; not the synthetic AI network |

Keep one Uvicorn worker: bus/event state and WebSocket revisions are in memory. Backend restart clears buses/scenarios. Restart after regenerating data or training, because successful model bundles and baseline datasets are cached.

## Verification

```sh
.venv/bin/python -B -m unittest discover -s backend/tests -v
.venv/bin/python -B -m unittest ml.synthetic.test_retraining -v
node scripts/test_phone_page.js
cd frontend
npm test
npm run build
```

Browser tests need local backend/frontend processes and installed Google Chrome. For the integrated synthetic feed on backend port 8024 and Vite port 5176:

```sh
# Backend, project-root terminal
GTFS_DIR=datasets/synthetic_chennai BUS_STALE_SECONDS=4 .venv/bin/python -B -m uvicorn app.main:app --app-dir backend --port 8024
# Frontend terminal
cd frontend
BUSSURE_BACKEND=http://127.0.0.1:8024 npm run dev -- --port 5176
# Another frontend terminal
E2E_FRONTEND=http://127.0.0.1:5176 E2E_BACKEND=http://127.0.0.1:8024 npm run test:e2e -- ai-system.spec.js demo-map.spec.js
```

The original passenger browser test needs a separate fresh SAMPLE backend (port 8025, `GTFS_DIR=simulator/routes/sample_gtfs GTFS_SAMPLE=1 BUS_STALE_SECONDS=4`) and Vite proxy (port 5177). Run `E2E_FRONTEND=http://127.0.0.1:5177 E2E_BACKEND=http://127.0.0.1:8025 npm run test:e2e -- passenger.spec.js`. Use separate feeds because the legacy fixture assertions intentionally test SAMPLE IDs.

## Troubleshooting

- 409 from AI search: restart with the exact generated synthetic GTFS; never rename an unrelated graph to force compatibility.
- `BASELINE_FALLBACK`: inspect the visible reason, install ML dependencies, verify artifacts, or regenerate/retrain after a source/GTFS change. Do not hide the fallback label.
- No journey: check direction, service date/time, transfer limits, walking radius, buffer and blocked segments. Out-of-area GPS may have no nearby synthetic stops.
- No vehicle: start the simulator with the matching dataset configuration. Wait for a fresh fix; stale and passed buses are not boarding candidates.
- Tiles missing: internet is needed for map backgrounds; marker/path data still comes from the local API.
- Device permission denied: re-enable browser location access on a secure origin. This prototype cannot bypass permission.

See [architecture](architecture.md), [model integration](model_integration.md), [datasets](datasets.md), [API reference](api_reference.md) and [test/status report](testing_report.md) for exact formulas, evaluated results and limitations.
