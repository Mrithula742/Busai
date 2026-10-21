# Dataset provenance and contracts

## Synthetic timetable and baseline observations

`scripts/generate_synthetic.py` uses seed 42 to write `datasets/synthetic_chennai/`. It contains seven approximate Chennai-area place anchors, six invented directional services, 320 daily trips and 10,080 hourly segment observations across 35 generated days. Services depart from 06:00 to before 22:00; end stops may be reached later. The generator writes all GTFS-inspired stops, routes, trips, stop times, daily calendar, shapes, manifest and simulator configuration. It never downloads operator data.

`stops.txt`: stop_id, stop_name, stop_lat, stop_lon. `routes.txt`: route_id, route_short_name, route_long_name, route_type. `trips.txt`: route_id, service_id, trip_id, shape_id. `stop_times.txt`: trip_id, arrival_time, departure_time, stop_id, stop_sequence. `calendar.txt`: service_id, seven weekday flags, start_date, end_date. `shapes.txt`: shape_id, latitude, longitude, ordered sequence. Shapes are generated curved connectors containing each stop anchor; they are synthetic route geometries, **not actual road alignments**. The simulator and selected itinerary use the same shapes.

`observations.csv`: day, route_id, from_stop, to_stop, hour, scheduled_minutes, ride_minutes, occupancy_ratio. Travel is in minutes; occupancy is a dimensionless 0–1 ratio. Peak hours and seeded noise determine values. The original baseline uses days 0–27 for training and 28–34 for testing. `/api/synthetic/*` preserves the original baseline functionality and metrics.

## Synthetic temporal graph dataset

`ml/synthetic/data.py` independently generates full-day temporal histories on the same graph. It does not pretend to turn the hourly observations into measured 5-minute records. Seed 42 and the timetable topology determine:

- Crowd: shape `[35 days,288 five-minute slots,7 ordered stops,8 features]`.
- Travel: shape `[35 days,96 fifteen-minute slots,18 directed route-segments,4 features]`.

Time is synthetic local-clock time; synthetic day 0 is assigned weekday index 0. Crowd occupancy follows an autoregressive process driven by morning/evening demand, node offsets and seeded noise. Boarding/alighting **ratios** are generated from occupancy changes plus turnover; they are not passenger counts. Travel follows a separate autoregressive process around scheduled segment duration and peak demand. All formulas live in the generator.

Split: days 0–20 train, 21–27 validation, 28–34 test. Windows never cross day boundaries. Per-node scalers use training days only. The application replays completed historical windows from test day 34 at the requested clock time. Crowd forecasts predict the next 5-minute slot; travel predicts the next 15-minute slot. The full-journey application of these values is a fixed-condition scenario assumption, not validation of a multi-hour forecast. Dataset/scaler/node/feature/source/GTFS contracts and SHA-256 hashes are stored in `ml/synthetic/artifacts/manifest.json`; temporal histories are `replay.npz`.

## Existing sample and presentation fixtures

`simulator/routes/sample_gtfs/` is the original explicitly fictional SAMPLE feed. `backend/app/data/chennai_demo.json` is the deterministic presentation scenario fixture. These remain available and separate from the new graph forecasts. They are not actual operator service data.

## Archived research datasets

`ml/crowd/training/results/` contains the earlier 10-node Salvador stop mapping, scalers, arrays, checkpoints and evaluation CSVs. `ml/travel_time/dcrnn_v2/sunt_dev_artifacts/` contains the saved nine-segment Salvador historical demonstration, node mapping, observation samples, manifest and reference predictions. Local provenance notes and model configs remain with those bundles. Their metrics and preprocessing contracts are not transferred to Chennai. Original data licensing/provenance should be reviewed from those records before redistributing archived data; no new external dataset was downloaded in this implementation.

## Limits

No synthetic bus ID is an actual MTC/TNSTC assignment. Stop anchors are not surveyed boarding positions, walking uses straight-line distance, and synthetic geometries are not road directions. No claim of real-world accuracy, crowd capacity measurement, traffic calibration or official GPS coverage follows from these datasets.
