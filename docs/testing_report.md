# Implementation and test report

**Latest extension:** the six-feature portfolio showcase is documented in [showcase_report.md](showcase_report.md), including the current 82 backend / 15 frontend / 8 browser test results. The report below preserves the preceding integration milestone.

Verified on 2026-10-17 in the existing BusSure workspace. No new project was created. The checkout has no Git repository metadata, so this report describes file/module changes rather than a commit diff.

## Implemented modules

- `scripts/generate_synthetic.py`: preserves original stops/routes/trip/observation counts and adds ordered synthetic GTFS shapes containing every stop.
- `ml/synthetic/data.py`, `models.py`, `train.py`, `artifacts/`: reproducible temporal synthetic data, a new seven-node ST-GCN, existing V2 DCRNN retrained on 18 mapped segments, strict manifests, scalers, replay histories and held-out evaluation. `original_artifact_inspection.json` records archived checkpoint tensor/config inspection.
- `backend/app/services/forecast_service.py`: validated CPU inference, inverse scaling, completed-bin replay, and explicitly named baseline fallback.
- `backend/app/services/ai_journey_service.py`, `disruption_service.py`, `backend/app/api/ai.py`: directed timetable/transfer search, approximate walking, GPS-based remaining-segment boarding estimates, scenario effects, reliability/risks/explanations, prediction/scenario/model APIs. Registered in `backend/app/main.py` without removing legacy routers.
- `simulator/multi_bus_simulator.py`, `network_event_hook.py`, GPS/event schemas: shape-following positions and headings, dwell, severity slowdowns/stops and accumulated scenario delay reported in GPS payloads. New event types retain original event creation/clear/WebSocket lifecycle.
- `frontend/src/components/AIWorkspace.jsx`, `aiWorkspace.css`, `services/ai.js`, Home/map markers: integrated responsive planner, results, itinerary, selected-journey navigation, 10-second refresh, source labels, scenario controls and model insights. Original baseline/fixture/historical sections remain accessible in collapsed panels. Legacy GTFS-only cards retain their original scope and are shown on Home.

## Evaluation actually obtained

New models use seed 42 and 18 epochs; validation selects the saved checkpoint. Train days 0–20, validation 21–27, test 28–34. Metrics below come directly from the generated artifact manifest.

| Synthetic model | Test MAE | Test RMSE | Persistence test MAE | Train / validation / test windows |
|---|---:|---:|---:|---|
| Seven-stop ST-GCN | 0.012526 occupancy ratio | 0.015753 ratio | 0.014889 ratio | 5796 / 1932 / 1932 |
| 18-segment DCRNN V2 | 0.558525 minutes per segment | 0.853830 minutes | 0.620956 minutes | 1932 / 644 / 644 |

These describe generated processes only. They do not establish Chennai operational accuracy. Original archived crowd/ETA metrics remain separately documented in `model_integration.md`. The historical DCRNN CLI reproduced its saved reference predictions for all nine segments.

## Executed checks

| Check | Actual result |
|---|---|
| Backend unittest discovery | 68 tests passed |
| Original DCRNN pipeline + SUNT extraction suites | 7 tests passed |
| Synthetic retraining reproducibility | 1 test passed; two temporary one-epoch runs produced identical weights/metrics |
| Frontend Node tests | 9 tests passed |
| Integrated AI desktop/mobile + preserved presentation-map Chrome tests | 3 tests passed |
| Original SAMPLE passenger desktop/mobile Chrome regressions | 2 tests passed |
| Phone-page Node harness | 7 mocked browser/GPS scenarios passed |
| Frontend production build | Passed; 104 transformed modules |
| Historical saved-sample inference | `saved_sample_reproduced=true`, nine segments |

Backend tests include checkpoint loading, graph/node/feature compatibility, artifact corruption rejection, inverse scaling, training-only scaler fitting, no future replay leakage, reproducible generation, explicit fallback, direct/reverse routes, one/two transfers, impossible/timetable-exhausted connections, transfer walking/buffers, walking origin, crowd/preference ranking, reliability formula, roadblock alternatives, congestion/crowd effects, spatial/segment/window scope, GPS remaining distance/staleness, synthetic motion/headings/dwell, API validation and original networking regressions.

The low-crowd Chrome flow searches Madipakkam → Kanchipuram, receives multiple feasible transfer options, selects an alternative, verifies that congestion raises the displayed ride estimate (transfer waiting can absorb some of that delay), observes changing simulator marker position, opens My Journey, observes the refreshed estimate timestamp, checks model insights, and activates/clears a scenario. Mobile checks confirm the integrated region does not overflow. The browser fixture deliberately uses faster simulated movement for observable pixel changes; this is not a performance or physical GPS claim.

A segment-window regression additionally checks a roadblock that starts and ends while a bus would be traversing the segment.

One original networking test explicitly asserted that roadblocks had no effect. Its assertion was updated to verify stopped motion and accumulated scenario delay as required by this implementation. Original passenger browser tests were updated to enter the existing landing screen; their networking and permission assertions were preserved. Browser verification caught and fixed a minute-only refresh timestamp; the initial test incorrectly expected it to change within 16 seconds. Map-movement assertions use the labelled accelerated test simulator rather than demanding pixel changes from a very slow bus at a city-wide zoom. A compile-cache check encountered sandbox write restrictions; Python syntax was checked by AST parsing without writing outside the workspace.

## Feature status

| Feature | Status | Scope / limitation |
|---|---|---|
| Existing baseline, sample feed, presentation scenarios | Completed and tested | Preserved APIs; earlier demos kept separate |
| Synthetic dataset generation | Completed and tested | Seven stops, six directional routes, 320 trips, 10080 hourly observations plus temporal ML histories |
| Synthetic ST-GCN inference + crowd API | Completed and tested | New implementation, seven stop nodes, 5-min replay forecast |
| Synthetic DCRNN V2 inference + ETA API | Completed and tested | Existing architecture, new 18-segment graph, 15-min replay forecast |
| Original DCRNN historical reference | Completed and tested | Separate Salvador-only demonstration |
| Direct use of archived crowd/ETA weights on Chennai | Blocked | Incompatible graphs/features; safe separate synthetic retraining implemented |
| Direct, one-transfer and two-transfer search | Completed and tested | Bounded simple paths; two-transfer algorithm tested on a controlled connected fixture |
| Nearby stops and walking time | Completed and tested | Haversine approximation, 1.4 m/s |
| Turn-by-turn pedestrian directions | Not implemented | No verified pedestrian network or directions engine |
| Synthetic GPS, route shapes, headings and dwell | Completed and tested | Generated shapes; not actual Chennai roads |
| Real-road simulator geometry | Not implemented | No authoritative road alignment was supplied/downloaded |
| Phone GPS sender, permission and stale handling | Partially implemented | Existing flow retained; automated protocol/GPS-double checks pass, physical-device run remains unverified |
| GPS-aware boarding estimates | Completed and tested | Fresh plausible upstream fixes near real server time; approximate remaining-segment fractions |
| Roadblocks/congestion/breakdown/rain/crowd scenarios | Completed and tested | Deterministic synthetic effects; no road diversion geometry or traffic calibration |
| Reliability, delay/transfer risks and explanations | Completed and tested | Transparent planning index/ranges; no probabilistic confidence claim |
| Preferences, results, selected map and My Journey refresh | Completed and tested | In-session selection, 10-second polling, stale-safe GPS stream |
| Model Insights | Completed and tested | Original/synthetic scope and evaluation separated |
| Live learned crowd/ETA from operational temporal feeds | Not implemented | Current deep models use saved synthetic test-day histories |
| Long-horizon calibrated journey forecasts | Not implemented | Short-horizon forecasts held fixed as explicit scenario assumptions |
| Authentication, database, durable selections/events | Not implemented | Local trusted-network prototype; one worker |

## Remaining issues and boundaries

The app is an integrated, tested **synthetic AI prototype**, not a deployed real-world operator service. Walking and geometry limitations, physical phone validation, operational temporal ingestion, calibration/uncertainty evaluation, durable storage and authentication remain. A bus simulator loops its assigned synthetic trip pattern independently of the timetable; GPS may be used as a continuous simulation boarding estimate near now, with its source shown. Restart clears state. Public map tiles require connectivity; no tile availability claim is made.

Exact startup and browser-test commands are in `synthetic_end_to_end.md`. Model architecture/contracts are in `model_integration.md`; source/schema/horizon details are in `datasets.md`; request/response contracts are in `api_reference.md`.

Screenshots from the successful integrated Chrome run: [desktop](verification/ai-system-desktop.png), [mobile](verification/ai-system-mobile.png). Temporary acceptance-test servers were stopped after verification.
