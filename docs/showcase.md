# BusSure portfolio showcase

This upgrade extends the existing synthetic AI prototype. Existing models, GTFS, simulator, networking, old planners and endpoints are retained. No LLM service, operational operator feed or new model training is introduced.

## Six connected features

| Feature | Implementation / source |
|---|---|
| Live Journey Digital Twin | `/api/twin` snapshots verified vehicle state, computes remaining/boarding ETA from fresh GPS and existing travel forecasts, and provides explicitly synthetic stop-occupancy proxies. WebSockets drive map movement and speed; estimate cards refresh every five seconds. Focus follows a chosen bus. SIMULATED and DEVICE GPS have separate labels/icons. Stale/disconnected/unmatched/blocked estimates are unavailable rather than fabricated. |
| Smart Journey Comparison | Every integrated plan includes computed fastest, least-crowded and most-reliable champions from the returned feasible candidates, metrics and ties. Cards expose duration/wait/transfer/crowd/reliability differences and highlight the selected preference's actual recommendation. These are not assertions of a global city-wide optimum. |
| What-If Simulation Studio | `/api/ai/what-if` computes before and after from one copied bus/event snapshot and copies of cached forecasts. Per-route travel is multiplied by traffic factor; extra route delay is divided across all directed route segments; passenger demand multiplies occupancy on the affected route only. Roadblocks remove affected segments. Worsening overlays add a deterministic scenario-risk marker. The overlay never creates persistent events, changes model weights or alters running GPS vehicles. Reset discards the preview; normal estimates stay independent. Existing global disruption controls remain available separately. |
| Natural-language assistant | `/api/assistant/interpret` uses a bounded rule grammar, exact catalog names/IDs and explicit Stop A–G aliases. It returns interpreted fields, missing details and warnings. Users confirm before planning; missing origins/destinations require a choice. No LLM or general conversation is claimed. |
| Model Performance Dashboard | `/api/models/evaluation` re-runs unchanged saved weights over all held-out windows for days 28–34. It returns actual, predicted and last-observation persistence values. MAE/RMSE use every test window/node; charts and accessible tables show 64 evenly spaced windows per selectable node. This is labelled held-out synthetic evaluation, never runtime ground truth. Archived original experiments stay in their own section. |
| Smart Boarding Alerts | In-app alerts for estimated boarding within three minutes, arrival shifts of at least five minutes, and an associated vehicle nearing a transfer stop. The pure alert engine uses timestamped GPS, selected itinerary, connection state and a recent successful plan update. Browser notifications are requested only by clicking Enable; denied/unsupported/failed delivery keeps in-app fallback. |

## Demonstration flow

1. Start the backend, simulator and frontend using `synthetic_end_to_end.md`. Open the workspace and AI Journey.
2. Enter `Take me to Stop G at 08:00 with low crowd and fewer transfers.` in the assistant. It asks for the starting stop. Choose Madipakkam and confirm. Stop G is an explicit demo alias for Kanchipuram, not an invented operational stop identifier.
3. Compare the fastest, least-crowded and most-reliable cards. Ties can choose the same journey. Select a route and open My Journey.
4. In What-If Studio, select an affected route, raise traffic or demand, add a delay or roadblock, and preview. Inspect matched ride/total/crowd/reliability deltas; reset. A delay can be absorbed by transfer waiting, so ride time can rise while final arrival stays the same.
5. Open Digital Twin to observe actual simulator updates following generated GTFS geometry. Focus a bus and inspect speed, next stop, fix/estimate timestamps, replay occupancy proxy and scenario delay. No official operator feed is implied.
6. Open Model Insights. Switch ST-GCN/DCRNN and graph nodes; inspect the held-out chart, persistence comparison and accessible values. Original research metrics are separate.
7. Select a journey near the real server clock for boarding alerts. Browser notifications are optional; location access is not notification access. Itineraries far from departure deliberately produce no approaching-bus alert.

## Assistant grammar

- `From <exact stop> to <exact stop>` or `Take me to <exact stop>`.
- `at 08:30` / `after 9 am` sets departure readiness; `by 10:00` / `before 10:00` is explicitly interpreted as an arrival deadline.
- `today`, `tomorrow`, `now`; absent time uses the visibly selected planner date/time.
- `low crowd`, `fewer transfers`, `most reliable`, `fastest`, `direct only`, `wait up to 10 minutes`.
- Multiple preferences follow textual order; subsequent preferences break primary ranking ties. Arrival deadlines and total maximum-wait constraints are enforced by the planner.
- Unknown places, missing essentials and invalid clock values are not guessed. Approximate/range expressions are flagged. It is a small grammar, not a language model. Review the interpreted fields before applying, especially deadline semantics.

Stop alias order is the dataset catalog order: A Madipakkam, B Velachery, C Guindy, D T Nagar, E Chennai Central, F Tambaram, G Kanchipuram. The API returns this mapping.

## Alert rules and limitations

A vehicle must be fresh, timestamp-valid, non-stale and connected; the last successful itinerary update must be within 45 seconds. Approaching alerts apply only when the first boarding time is within 15 minutes of the current clock and a fresh route-matching vehicle has a boarding estimate at most three minutes. Transfer reminders additionally match the assigned bus or exact trip, next stop and a plausible arrival-time window. ETA changes compare successive refreshed arrival estimates, with a five-minute threshold.

Logical alert IDs include selected itinerary and requested departure session. Approaching/transfer alerts are issued once per session/bus/stop or transfer. Dismissal does not reset deduplication; navigation preserves it within the workspace session. In-app notices expire after three minutes. Refreshing the browser clears this in-memory history. This is not an OS background push/service-worker system and is not a safety-critical transit alert service.

## Provenance and presentation

Forest-green cards, navy text, white surfaces and amber simulation highlights share the existing design. Controls, tables and charts support narrow screens; motion respects reduced-motion preferences. Generated route shapes are not real roads. Occupancy remains a stop-load proxy, not a measured onboard count. The new screens do not upgrade the original models' real-world validity or prediction horizon.

README contains screenshots from successful automated Chrome runs. Model weight files and training source/contracts are unchanged; `.gitignore` now explicitly allows the two small synthetic inference checkpoints so a future GitHub checkout can include them. This workspace has no Git repository metadata; no remote repository or LinkedIn publication was created.

## New APIs

- `GET /api/twin?boarding_stop=VEL`: current vehicle snapshot and nullable, source-labelled estimates. Requires the matching active synthetic network. Outside 06:00–21:59 IST, vehicle tracking remains visible but replay forecasts are unavailable.
- `POST /api/ai/what-if`: `{journey: <existing journey body>, route_id, traffic_factor: 1..3, demand_factor: 0.5..2, delay_minutes: 0..60, roadblock: boolean}`. Returns before/after results and matched deltas. Nothing to reset on the backend because no shared state is written.
- `POST /api/assistant/interpret`: `{text, departure_time?: <offset-aware timestamp>}`. Returns RULE_BASED parameters, aliases, missing_fields, warnings and ready.
- `GET /api/models/evaluation?model=crowd|eta`: cached full-test metrics and sampled per-node actual/predicted/persistence series. Missing/incompatible artifacts return 503.
- Existing `/api/ai/journeys` accepts optional `secondary_preferences`, offset-aware `arrival_deadline`, and `max_wait_minutes` (total wait). Its response additionally includes comparison cards. All previous request fields/endpoints remain supported.
