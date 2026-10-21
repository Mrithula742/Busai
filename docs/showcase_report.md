# Showcase implementation and verification report

Verified 2026-10-17 in the existing BusSure workspace. This extends the integrated synthetic prototype; no model checkpoint was replaced or retrained for the application. SHA-256 checks confirm every existing synthetic bundle artifact remains unchanged.

## Feature delivery

| Requested feature | Status | Verified scope |
|---|---|---|
| Live Journey Digital Twin | Implemented and tested | Geometry-following existing simulator; WebSocket marker/speed updates; five-second API estimate snapshots; next stop, occupancy proxy, next-stop/boarding ETA, scenario delay, stale/disconnected state; source labels and map focus |
| Smart Journey Comparison | Implemented and tested | Three computed category champions, ETA/duration/wait/transfers/crowd/reliability, recommendation highlighting, ties and duration trade-offs |
| What-If Simulation Studio | Implemented and tested | Backend traffic/demand/delay/roadblock adjustments, before/after and matched deltas, reset, route scoping and no shared-state/model mutation |
| Natural-Language Journey Assistant | Implemented and tested | Explicit rule grammar, exact catalog and documented Stop A–G aliases, origin/destination/time/priority/constraint extraction, missing detail selection and confirmation before planning |
| AI Model Performance Dashboard | Implemented and tested | Unchanged ST-GCN and DCRNN inference over held-out test data; actual/predicted/persistence chart and accessible table, node selection, MAE/RMSE and counts; original research remains separate |
| Smart Boarding Alerts | Implemented and tested | Approaching, major arrival change and transfer rules; timestamp/freshness/connection checks; departure-session deduplication; explicit notification permission and denied-delivery in-app fallback |

Native OS notification delivery and physical phone GPS hardware remain environment-specific and are not claimed as verified. Browser permission/delivery behaviour was tested with explicit browser API doubles; alert generation is separately tested from real timestamped itinerary/vehicle contracts.

## Files added

- `backend/app/api/showcase.py`: twin, what-if, assistant and model-evaluation endpoints.
- `backend/app/services/showcase_service.py`: computed comparison and route-scoped copied scenario forecasts.
- `backend/app/services/assistant_service.py`: bounded grammar and clarification contract.
- `backend/app/services/evaluation_service.py`: full held-out inference/metrics plus sampled node series.
- `backend/tests/test_showcase.py`: 14 new tests covering these backend features.
- `frontend/src/components/ShowcasePanels.jsx`, `showcase.css`: six responsive panels and related states.
- `frontend/src/services/boardingAlerts.js`: pure in-session alert/freshness/deduplication rules.
- `frontend/tests/boardingAlerts.test.js`: six alert engine tests.
- `frontend/tests/browser/showcase.spec.js`: three new browser acceptance tests.
- `docs/showcase.md`, this report, and verified screenshots in `docs/verification/showcase-*.png`.

## Existing files updated

`backend/app/main.py` registers the new router. `api/ai.py` accepts optional secondary preferences, arrival deadline and total-wait limits, and enriches results with comparison cards. `ai_journey_service.py` applies those constraints and route-specific scenario demand. `disruption_service.py` recognizes an internal neutral scenario-risk marker without double-applying travel or occupancy effects.

`frontend/src/components/AIWorkspace.jsx` integrates new API state and screens while retaining all existing planners and model insights. `MapView.jsx` supports following a selected vehicle. `pages/Home.jsx` exposes Digital Twin and Simulation Studio navigation. `README.md`, startup/API/architecture documents and `.gitignore` explain the showcase and allow the two small synthetic inference checkpoints into a future Git checkout. Existing test output directories are ignored.

## Actual tests executed

| Check | Result |
|---|---|
| Backend unittest discovery | **82 passed** (all previous 68 + 14 new) |
| Existing DCRNN pipeline and SUNT tests | **7 passed** |
| Synthetic retraining reproducibility | **1 passed**, temporary output only; application weights unchanged |
| Frontend Node tests | **15 passed** (previous 9 + 6 alert tests) |
| Existing AI journey + presentation Chrome tests | **3 passed** |
| New showcase Chrome tests | **3 passed** |
| Original SAMPLE passenger Chrome tests | **2 passed** |
| Phone-page mocked harness | **7 scenarios passed** |
| Vite production build | **Passed**, 107 modules transformed |
| Python syntax / preserved synthetic artifact integrity | **Passed** |

Backend tests verify real computed comparison minima/maxima, scenario route isolation, forecast/cache immutability, unchanged global event state, identity/reset equivalence, roadblock exclusion, crowd decrease without an invented risk penalty, input bounds, assistant missing details/time/aliases/priority order, actual deadline/wait filtering, held-out metrics against saved results and actual target arrays, twin source/speed/ETA/occupancy and stale-null behaviour.

Chrome tests verify: assistant asks for missing origin and drives planning; three comparison cards select a journey; studio preview/reset and API error recovery; moving simulated bus markers and map focus; both model charts, node selection and all 64 displayed values; no notification request before a user click; denied-permission fallback; in-app approaching alert rendering and no repetition after dismissal/refreshed estimates; mobile region and document overflow checks. The alert UI delivery test uses an explicitly controlled timing/vehicle fixture around normal FastAPI journey results; it is not evidence of observed physical bus arrival.

The old regression tests still cover passenger GPS permission, WebSocket reconnect/snapshot resync, events and stale tracking. Existing historical and synthetic model performance numbers were not relabelled or fabricated.

## Re-run

From project root:

```sh
.venv/bin/python -B -m unittest discover -s backend/tests -v
.venv/bin/python -B -m unittest ml.travel_time.dcrnn_v2.test_pipeline ml.travel_time.dcrnn_v2.test_sunt ml.synthetic.test_retraining -v
node scripts/test_phone_page.js
```

From frontend:

```sh
npm test
npm run build
```

For the six synthetic/showcase Chrome tests, run a fresh backend on 8030 with `GTFS_DIR=datasets/synthetic_chennai BUS_STALE_SECONDS=4`, and Vite on 5180 with `BUSSURE_BACKEND=http://127.0.0.1:8030`. Then:

```sh
E2E_FRONTEND=http://127.0.0.1:5180 E2E_BACKEND=http://127.0.0.1:8030 npm run test:e2e -- showcase.spec.js ai-system.spec.js demo-map.spec.js
```

For the original passenger suite use a separate fresh backend on 8031 with `GTFS_DIR=simulator/routes/sample_gtfs GTFS_SAMPLE=1 BUS_STALE_SECONDS=4`, and Vite on 5181 targeting it. Then:

```sh
E2E_FRONTEND=http://127.0.0.1:5181 E2E_BACKEND=http://127.0.0.1:8031 npm run test:e2e -- passenger.spec.js --output=test-results-legacy
```

Google Chrome is required by the existing Playwright configuration. Port values can be changed together if occupied. Acceptance tests use clearly synthetic accelerated simulation and separate feeds; do not run destructive test fixtures against a production backend.

## Model/provenance boundaries

Existing synthetic ST-GCN test MAE remains 0.012526 occupancy ratio; DCRNN V2 remains 0.558525 minutes per segment. Persistence MAEs remain 0.014889 ratio and 0.620956 minutes. Recomputed full-test metrics match the saved manifest within tested numerical tolerance. Charts sample 64 evenly spaced windows; metrics use all test windows/nodes. These scores establish reproduction of generated patterns only.

The digital twin is GPS state plus replay-based estimates, not a live onboard occupancy sensor. No estimates are invented for stale, blocked, unmapped or unsupported-clock inputs. What-if adjustments are deterministic scenario formulas, not a new trained causal traffic model. Their before/after calculations hold the query, copied vehicle state and existing events fixed. Alerting is a foreground/in-session feature; no service worker/background push was added.

## Remaining limitations

Actual-road routing and pedestrian directions, operational time-series ingestion, calibrated uncertainty, durable state/authentication, physical-phone verification and native OS notification delivery remain unverified or outside this upgrade. The assistant supports its documented grammar, not arbitrary natural language. GitHub/LinkedIn publication is not performed; there is no Git metadata or remote configured in this workspace. The README, screenshots, source and demonstration guide are prepared for a user-led showcase.

## Suggested project description (not published)

> BusSure is an explainable public transport planning prototype combining ST-GCN crowd and DCRNN travel forecasts with GTFS-inspired transfer planning, a GPS digital twin, isolated what-if scenarios and transparent reliability factors. Its responsive React/FastAPI application includes a rule-based assistant, held-out performance dashboard and timestamp-aware boarding alerts. All showcased Chennai services and model histories are synthetic; sources and limitations are labelled throughout.
