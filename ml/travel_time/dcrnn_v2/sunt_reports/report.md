# SUNT → existing BusSure DCRNN V2

## Result

A small real SUNT development experiment is complete. The existing DCRNN V2
architecture, window generator, scaler and trainer were reused unchanged.
The extracted source folder was read directly. Neither the 8.69 GB ZIP nor the
full dataset was copied or extracted. No full-network training was started.

The final model uses 8,132 derived traversals on 9 connected segment nodes.
Three CPU epochs took 3.43 seconds and peaked at 299.30 MiB resident RAM.
Test MAE is 6.75 seconds, compared with 9.62 seconds for persistence.
The target is an **AVL-derived stop-transition estimate**, not verified door-event
arrival/departure ground truth. The bundle is explicitly marked `production_ready: false`.

## 1. Source directory structure and sizes

Source: `/Users/mrithula/Downloads/Salvador Urban Network Transportation (SUNT)`.
Sizes below are decimal bytes/GB; RAM measurements use binary MiB.

| Directory | Files | Total bytes | Format / purpose |
| --- | ---: | ---: | --- |
| `AVL/` | 686 | 3,507,172,971 | 343 pairs of daily vehicle/line Parquet files |
| `AFC/` | 362 | 5,851,893,799 | Daily fare-validation Parquet files; not used for travel-time labels |
| `GTFS/BUS/` | 13 | 109,568,968 | GTFS CSV text tables and one small exploratory notebook |
| `GTFS/BRT/` | 7 | 176,064 | GTFS text tables |
| `Boarding/`, `Alighting/`, `OD/` | 1 each | 393 combined | Markdown pointers to external datasets |

The folder totals about 9.47 GB including metadata. The separate ZIP is
8,686,933,495 bytes; only its file size was inspected. There are no nested archives
in the extracted folder. [file_inventory.csv](file_inventory.csv) lists every
filename, size and extension. No large source file was loaded as a whole table.

## 2–3. Important files and safely inspected schemas

| File | Bytes | Rows when cheaply counted |
| --- | ---: | ---: |
| `AVL/avl-vehicles-2024-05-21.parquet` | 13,023,861 | 2,704,823, from Parquet footer |
| `AVL/avl-lines-2024-05-21.parquet` | 453,478 | 212,730, from footer |
| `AFC/afc-2024-03-01.parquet` | 20,505,591 | 1,420,338, from footer |
| `GTFS/BUS/stops.txt` | 368,013 | 2,975 |
| `GTFS/BUS/routes.txt` | 28,221 | 412 |
| `GTFS/BUS/trips.txt` | 5,343,530 | 51,615 |
| `GTFS/BUS/stop_times.txt` | 87,691,407 | Filtered in 8,192-row chunks; no full table retained |
| `GTFS/BUS/shapes.txt` | 16,073,057 | Header only; not needed for this segment graph |
| `GTFS/BUS/calendar.txt` | 50,291 | 1,034 |

BUS stop records contain 2,867 stops and 108 parent stations. BRT has 21 stop
records, 4 routes and 412 trips. Global unique segment count was not computed;
the experiment's topology and retained graph are counted exactly.

All GTFS headers, representative Arrow schemas and selected-source sizes are saved
in [schemas_and_sizes.json](schemas_and_sizes.json). Schema variations are real:
March's AVL sample has eight fields; May 21 also contains `TipoViagem`,
`DataHoraGPSEntrada` and `DataHoraGPSSaida`. The adapter selects only its six
required columns and tolerates the unused extra fields.

| Required meaning | Available data |
| --- | --- |
| Measured bus observations | Daily `avl-vehicles-*.parquet` |
| Date/time | `gps_datetime`, timezone-naive `timestamp[ms]` |
| Vehicle | `vehicle`, int32 |
| Route | `route_short_name`, string; joined to GTFS route short name |
| Direction | `direction_id`, locally stored as `I` / `V` |
| Service pattern | `service_code`, uint32 |
| Stop | `stop_id`, uint32 in vehicle files; some line files use floating IDs |
| Coordinates | `latitude`, `longitude`, float32 |
| Segment ID | No raw segment column; derived as directed consecutive GTFS stop pair plus route ID |
| Explicit measured travel seconds | Not present |
| Arrival/departure | Extra May fields exist but only 6,812 / 2,704,823 records have nonnull values on May 21; not used |
| Ordered topology | AVL-lines `pt_sequence` plus GTFS `stop_sequence` / `shape_id` |
| Actual GTFS vehicle trip | Not explicitly available in AVL; a GTFS trip is used only as a topology template |

AVL-lines also has route descriptions, stop coordinates and daily service patterns.
AFC has `cod_card`, `afc_datetime`, `integration`, `route_short_name`, `direction_id`,
`value`, `vehicle`. AFC passenger records are unnecessary here and were not read.

## 4–5. Target and feature selection

The SUNT authors describe `gps_datetime` as stop arrival and/or departure observation
times, and `stop_id` as the stop associated with a record. See the
[official SUNT field documentation](https://github.com/LabIA-UFBA/SUNT/blob/main/docs/datasets.md).

For one vehicle on the selected route, direction and service pattern, repeated
observations at an upstream stop are collapsed to the last timestamp. The next
recognized adjacent GTFS stop supplies the first downstream timestamp. Their
difference is a travel-time **proxy**, with sampling uncertainty. It may include
dwell at extra AVL stops between the two GTFS anchors. It is not a verified
door-open/door-close duration. That limitation is saved with the checkpoint.

Extraction rejects skipped/reversed GTFS transitions, noncontiguous source-record
runs, durations outside 5–900 seconds, and straight-line minimum speeds above
35 m/s. State is reset for each vehicle/day; there are no overnight joins. Records
outside their source file's calendar date are excluded. Any extra non-GTFS records
between anchors are counted, not silently treated as missing topology.

The native timestamps have no zone. The adapter explicitly adopts the BUS agency
timezone, `America/Sao_Paulo`, and V2 converts them to UTC. This is a documented
source-timezone assumption; an offset does not affect elapsed durations, but does
affect clock features and split timestamps.

The exact existing V2 feature order is retained:

1. `travel_time_z`: causal, per-node standardized historical bin mean.
2. `observed`: whether the bin contains a derived traversal.
3. `hour_sin`.
4. `hour_cos`.
5. `weekday_sin`.
6. `weekday_cos`.

Speed, dwell and headway are not invented as measured feature columns. GPS
coordinates are available, but are not added to the existing model contract.

## 6–8. Matching topology and connected subset

The BUS feed covers May 21–June 21, 2024. The selected period is May 21–June 3,
2024, wholly inside that interval. Route short name `1386` maps uniquely to
GTFS route `5898`: Nova Brasília/Jd.Nova Esperança/Sete Abril x Barra.
AVL service `12550`, direction `I`, matches GTFS shape `12550_I`. Its selected
ordered stop chain was checked against the daily AVL-lines file on all 14 days.

GTFS trip `1046876_D_1_0` supplies the ordered topology. This is **not** a claim
that each observed bus was operating that particular scheduled trip or calendar.
`trip_id_role` and the original service/vehicle provenance preserve this distinction.

The initial first-21-stop candidate produced 12,375 transitions on up to 20
segments. Some segments lacked training coverage, so the longest eligible
contiguous chain was selected using TRAIN bins only. Selection was rechecked
against the final split cutoff after filtering. No validation/test target values
were used to choose the graph. The retained chain is:

```text
45834097 → 44782442 → 47566681 → 44783270 → 47568385
         → 44784196 → 44784333 → 44782447 → 45833333 → 44784053
```

This gives **9 directed segment nodes and 8 connecting edges**, using **8,132
observations**. This is why the development graph is smaller than the initial
20-node proposal. Node-to-index order, adjacency and both diffusion supports are
saved by the existing trainer.

## 9–12. Configuration, memory and disk

| Item | Final development configuration |
| --- | --- |
| Model | Existing DCRNN V2, 24,929 trainable parameters |
| Input | `(batch, 12, 9, 6)` |
| Output | `(batch, 1, 9)` |
| History | 12 × 5-minute bins = 60 minutes |
| Horizon | Next 5-minute bin |
| Target aggregation | Mean derived segment duration for traversals completed in the target bin |
| Split | Chronological 70% / 15% / 15% |
| Windows | 1,278 train / 207 validation / 209 test |
| Validation starts | May 30, 2024, 22:20 UTC |
| Test starts | June 1, 2024, 23:55 UTC |
| Observation coverage | 21.84% of node-time cells have a label; other labels are masked |
| Batch / hidden / layers | 16 / 16 / 2 |
| Diffusion steps / dropout | 2 / 0.1 |
| Epochs / seed | 3 / 42 |
| Device | CPU, one PyTorch thread |

Pre-training budget: under 500 MiB preprocessing RAM, under 1 GiB training RAM,
under 30 MB for derived data and artifacts. Measured preprocessing peak was
**128.75 MiB**; training peak was **299.30 MiB**. Arrow reads use 8,192-row batches,
selected columns, and one filtered route-day at a time (maximum retained rows:
100,000/day). Row counters are incremental. The compact subset allows the existing
train-only float32 scaler fitting to remain unchanged. Windows are sliced lazily;
no array containing all overlapping windows is materialized.

The source scan covered 32,427,202 vehicle records over the selected dates, retaining
294,874 route/direction/service records before transition extraction. The 28
vehicle/line source files total 160,375,127 bytes and stayed in Downloads.

Additional small data/artifact storage is about **5 MB**:

- Candidate subset and audit: 1.98 MB.
- Connected subset and audit: 1.30 MB.
- Complete development model bundle: 1.67 MB.
- Inventory, schemas, plan and inference reports: under 0.1 MB before this prose report.

The added Parquet dependency, PyArrow 19.0.1, occupies about 109 MB in `.venv`
(its downloaded wheel is about 31 MB and may also remain in pip's cache). Existing
PyTorch/NumPy/Pandas packages were reused. No multi-GB processed copy was created.

## Development results and reproducibility

| Metric | Validation | Held-out test |
| --- | ---: | ---: |
| DCRNN MAE (seconds) | 8.4133 | 6.7518 |
| Persistence MAE (seconds) | 12.4502 | 9.6231 |
| DCRNN RMSE (seconds) | 27.1864 | 13.5102 |
| DCRNN R² | 0.1561 | 0.4047 |
| DCRNN WAPE (%) | 27.3810 | 22.8594 |
| Observed target cells scored | 913 | 910 |

Best epoch: 3. Fresh-process inference reproduced the saved held-out sample.
Example segment `44782442 → 47566681`: **41.83 seconds (0.697 minutes)**,
with one observed input bin in that sample's 12-bin history. This is a segment
duration forecast, not whole-journey or remaining-distance ETA.

Seven unit/integration tests passed. They cover the existing V2 pipeline plus
last-observation/first-observation extraction, skipped-stop rejection, source
discontinuities, gap bounds, timezone localization and chunk-row continuity.

The V1 checkpoint hash remains:
`8435e95b2d7c6db7493adc4add99f659c316ec4ad288d393557d86065ba5db86`.

Saved outputs:

- [Checkpoint](../sunt_dev_artifacts/dcrnn_v2_best.pt).
- [Training metrics and measured resource usage](../sunt_dev_artifacts/sunt_experiment.json).
- [Source, mapping, extraction and target provenance](../sunt_dev_artifacts/sunt_provenance.json).
- [Final experiment plan](experiment_plan.json).
- [Fresh-process inference result](inference_sample.json).

## Reproduce from the project root

```bash
.venv/bin/python -m pip install -r ml/travel_time/dcrnn_v2/sunt_requirements.txt

.venv/bin/python -m ml.travel_time.dcrnn_v2.sunt_inspect \
  --source '/Users/mrithula/Downloads/Salvador Urban Network Transportation (SUNT)' \
  --output ml/travel_time/dcrnn_v2/sunt_reports --schemas

# The following commands require NEW output directories; existing results are protected.
.venv/bin/python -m ml.travel_time.dcrnn_v2.sunt_prepare \
  --source '/Users/mrithula/Downloads/Salvador Urban Network Transportation (SUNT)' \
  --output ml/travel_time/dcrnn_v2/sunt_subset

.venv/bin/python -m ml.travel_time.dcrnn_v2.sunt_select_connected \
  --subset ml/travel_time/dcrnn_v2/sunt_subset \
  --output ml/travel_time/dcrnn_v2/sunt_connected_subset

.venv/bin/python -m ml.travel_time.dcrnn_v2.sunt_experiment \
  --subset ml/travel_time/dcrnn_v2/sunt_connected_subset \
  --output ml/travel_time/dcrnn_v2/sunt_dev_artifacts

# Runs now, with the saved bundle; does not require the full SUNT folder.
.venv/bin/python -m ml.travel_time.dcrnn_v2.inference \
  --artifacts ml/travel_time/dcrnn_v2/sunt_dev_artifacts --sample

.venv/bin/python -m unittest \
  ml.travel_time.dcrnn_v2.test_pipeline ml.travel_time.dcrnn_v2.test_sunt -v
```

All adapters are new files; the DCRNN architecture and original V2 processing
implementation were not rewritten. The `.gitignore` exception includes the new
development checkpoint so its complete bundle can be committed together.

## Stop before full-network training

This development result does not establish all-route accuracy or true arrival-time
ground truth. Full-network SUNT training has **not** been launched. The current
V2 dense graph supports and in-memory compact timeline should not be fed the
whole SUNT network/year on this 8 GB Mac. See the [cloud setup](../SUNT_CLOUD.md)
for a runnable bounded cloud experiment and the required sizing gate before
expanding to full-network work.
