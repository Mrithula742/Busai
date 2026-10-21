# API reference

Interactive OpenAPI: http://127.0.0.1:8000/docs. Existing GPS, GTFS, networking, WebSocket, fixture-demo and historical-model APIs retain their contracts; see root README and `docs/api_design.md` for legacy details.

| Endpoint | Purpose |
|---|---|
| `POST /api/ai/journeys` | Integrated direct/transfer search, forecasts, risk, explanation, itinerary |
| `POST /api/predict/eta` | Next-15-minute-bin synthetic segment travel-time forecasts |
| `POST /api/predict/crowd` | Next-5-minute-bin synthetic stop occupancy forecasts |
| `GET /api/models/insights` | Synthetic model status/evaluation, original experiment separation |
| `POST /api/simulation/scenarios` | Activate a labelled synthetic disruption through the event system |
| `POST /api/network-events/{event_id}/clear` | Clear a disruption and broadcast its new state |
| `GET /api/network-events` | Active/optionally cleared events |
| `POST /api/buses/location` | Validated phone or simulator GPS ingestion |
| `GET /api/buses`, `GET /api/snapshot`, `WS /ws/buses` | Vehicle state and revisioned updates/resync |
| `GET /api/stops/nearby` | Approximate nearby-stop distance and walking time |
| `GET /api/synthetic/catalog`, `POST /api/synthetic/journey` | Preserved original baseline experiment |

## Integrated search

```json
{"origin":"MAD","destination":"KAN","departure_time":"2026-10-17T08:00:00+05:30","preference":"less_crowd","max_transfers":2,"transfer_buffer":5}
```

Supply stop ID or exact stop name. Alternatively omit origin and supply latitude/longitude with walking_radius (default 1000 m, maximum 5000). The origin modes are mutually exclusive. `departure_time` requires an offset and is evaluated in IST, 06:00–21:59. Transfer walking radius defaults to 500 m (0–1000). Max transfers is 0–2; transfer buffer is 2–30 minutes. Preferences: faster, less_crowd, less_delay, fewer_transfers, most_reliable. Calendar service dates apply.

Response: source/mode/model metadata; options; recommended_option_id; message; tracking/walking policies. Each option includes ordered ride legs with actual trip IDs, boarding/alighting/time/wait source and optional qualifying bus; typed itinerary steps; geometry; walk/wait/ride/total/arrival; occupancy and crowd class; delay and transfer risks; deterministic reliability score and penalty breakdown; explanatory factors and scenario duration range.

422 means invalid input; 409 means the active GTFS does not match the synthetic model network. Zero feasible options is a successful response with an explanation. Missing deep models use labelled baselines; missing underlying synthetic dataset yields 503. Search is bounded at 5000 expansions and returns at most 12 distinct results.

## Forecast requests

ETA: `{"hour":8,"minute":0,"route_id":"SYN_A"}`. Omit route_id for all 18 segments; only a selected route has an aggregated route_travel_minutes value. Crowd: `{"hour":8,"minute":0,"stop_id":"MAD"}`. Omit stop_id for all seven stops. Hour 6–21, minute 0–59. Unknown mapped IDs return 422. Both return source, model, mode, fallback reason, replay history source and prediction horizon. ETA values are minutes/seconds, crowd ratios are dimensionless 0–1. Standalone forecasts are before scenario adjustments; integrated journey results include scenario effects.

## Synthetic scenario request

```json
{"route_id":"SYN_A","event_type":"CONGESTION","severity":"HIGH","duration_minutes":30}
```

Types: ROAD_BLOCK, CONGESTION, BREAKDOWN, TEMPORARY_DELAY, HEAVY_RAIN, CROWD_SURGE. Severity LOW/MODERATE/HIGH/CRITICAL; duration 1–180 minutes. Returns a 201 event with `SYN_SCENARIO_` ID and explicit synthetic description. Uses the server's real current clock; to observe impacts, choose a search whose segment traversal overlaps the event window. Existing general event API also accepts location-only, route, trip or segment scope and scheduled future windows. Segment IDs follow `route:from:to`; unknown scopes do not magically affect unrelated routes.

These APIs are for trusted local development and do not implement authentication or persistent storage.


## Showcase APIs

`GET /api/twin?boarding_stop=VEL`, `POST /api/ai/what-if`, `POST /api/assistant/interpret`, and `GET /api/models/evaluation?model=crowd|eta` extend the existing API. Journey bodies additionally support `secondary_preferences`, `arrival_deadline` and total `max_wait_minutes`; responses include computed `comparison` cards. Contracts, input bounds, simulation formulas, null/503 behaviour, assistant grammar and notification rules are documented in [showcase.md](showcase.md). Studio previews have no shared state and never modify the event stream or checkpoints.
