# Chennai bus stops and routes

The local application now runs with `datasets/gtfs`, using the MTC bus feed published by [UngalSoththu / ChennaiGTFS](https://github.com/ungalsoththu/ChennaiGTFS). The publisher describes its MTC source as the official MTC app, collected in April 2026. This is a community-published static feed, not a live operator feed. Route numbers, names, stop coordinates and schedules come directly from the downloaded files; no synthetic routes are renamed into real services.

The installed snapshot has 5,580 stop records and 4,611 directional route records. M1 is present; the 14M services are labelled S14M and S14M CT in this feed. These names are preserved. Coverage is the Chennai metropolitan service area, including adjoining areas, rather than a district-boundary filter. Published schedules may have changed; the current planner does not evaluate service calendars.

Download and run from the project root:

```sh
.venv/bin/python scripts/fetch_chennai_gtfs.py
.venv/bin/python -B -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

GTFS files live in the existing ignored local dataset directory. Downloading them does not replace the synthetic AI dataset or model artifacts. The AI showcase now loads an isolated synthetic network, bus store and event store alongside the real feed; real GTFS does not make those model outputs real MTC predictions.

Nearby Stops and Live Map show bus-stop icons from the loaded feed in the visible map bounds, grouped into count markers at city scale. Click a group or zoom in to reveal individual stops, even before geolocation is granted. Hover for stop name and served bus numbers; tap/click for a persistent popup and stop details. Grant location for walking distances and nearby results. Routes supports searching numbers or destinations and loads results in groups of 60.

The presentation planner displays bus labels M1, 14M and 21G for its internal synthetic routes. These do not map the illustrative itineraries to actual MTC services. The expandable calculation details describe the estimate source. Named origins include explicit 3/5/2-minute route-specific access walks before timetable boarding; GPS origins retain distance-based walking. Presentation crowd assumptions scale the saved occupancy replay by route (0.65/1.2/0.8), and studio demand multiplies these assumptions. These are scenario inputs, not new model predictions or sensor measurements. Distinct comparison cards select the fastest journey, the least crowded remaining journey, and the most reliable remaining journey; alternative headings distinguish these from a global optimum.
