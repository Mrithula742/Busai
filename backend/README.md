# Backend

See the root [README](../README.md) for installation, sample and real-GTFS startup, curl tests, phone HTTPS setup and verification.

Run one Uvicorn worker. FastAPI lifespan loads GTFS and starts stale detection and event expiry; bus updates and subscriber queue changes run on the same event loop without blocking network writes. Each viewer has a bounded queue and send timeout. GPS ingestion uses REST; `/ws/buses` sends bus-location, bus-status and network-event deltas. `/api/snapshot` provides atomic resync state with a server epoch and monotonic revision.

Configuration: `GTFS_DIR` (defaults to `datasets/gtfs`), `GTFS_SAMPLE=1` to permit labelled sample fallback when actual data is unavailable, `BUS_STALE_SECONDS=45`, `WALKING_SPEED_MPS=1.4`, `STOP_RADIUS_METERS=40`, `MAX_STOP_ACCURACY_METERS=100`. Relative custom GTFS paths resolve from your current working directory. Supplied real data takes priority over a sample request.

No database or ML runtime is required. State is lost on restart. The API is a local development prototype without authentication.
