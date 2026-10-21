# BusSure DCRNN V2

V2 is a new, independently specified diffusion recurrent model. The archived
`../dcrnn_v1_final_best.pt` is preserved and is never loaded or overwritten here.

## Current data status

**Update:** the external Salvador Urban Network Transportation (SUNT) dataset is
now connected through a bounded adapter. A small real-data experiment and saved
checkpoint are available in `sunt_dev_artifacts/`. See the
[SUNT inspection and experiment report](sunt_reports/report.md) for source schemas,
memory measurements, results and the limitations of its AVL-derived travel-time
labels. The original DCRNN V2 implementation remains unchanged.

The initial repository-only inspection found **zero recorded travel-time observations**. The
`datasets/raw`, `datasets/processed`, `datasets/sample`, and configured GTFS
directories contain no usable training data. GPS ingestion keeps the latest bus
state in memory; it does not provide a historical AVL dataset on disk.

The only GTFS is `simulator/routes/sample_gtfs`, explicitly marked `SAMPLE`:
5 stops, 3 routes, 6 trips, 18 stop-time rows. Its topology would give 6 directed
route-segment nodes (4 unique stop pairs), but its 12 scheduled traversals are
fictional schedules, not measured travel times. They are not used for training.
Crowd arrays do not provide travel-time supervision.

The original generic `artifacts/` output has not been created; SUNT development
results use their own directory and are not marked production-ready. Integration
tests train small synthetic fixtures only in temporary directories, then delete
their checkpoints. Their outputs are software verification, not bus predictions
or evidence of model accuracy on real trips.

## Prediction contract

| Item | V2 definition |
| --- | --- |
| Input data | Completed, measured traversals of consecutive GTFS stops |
| Node | `(route_id, from_stop_id, to_stop_id)`; distinct directions/routes stay distinct |
| Graph | Edges between consecutive segments on actual GTFS trips; no bridging over omitted segments |
| Supports | Forward and reverse row-normalized random walks with self loops; isolated nodes remain valid |
| Nodes selected | Segments with at least 5 observed TRAIN bins, configurable; order sorted and saved |
| Target | Next-bin mean measured traversal seconds, grouped by arrival/completion timestamp |
| Observation duration | Downstream arrival minus upstream departure; excludes upstream dwell |
| Time bins | 5 minutes, UTC, left-closed/right-open |
| History / horizon | 12 bins (60 minutes) / 1 bin (next 5 minutes), configurable |
| Features | `travel_time_z`, `observed`, `hour_sin`, `hour_cos`, `weekday_sin`, `weekday_cos` |
| Input / output | `(B, 12, N, 6)` / `(B, 1, N)` with default configuration |
| Split | Chronological 70% train, 15% validation, 15% test by time bins |
| Missing inputs | Causal forward fill, then training median before the first available observation; mask records missingness |
| Missing labels | Excluded from loss and metrics, never imputed as supervision |
| Scaling | Per-node mean/population std fitted only on observed TRAIN bin means |
| Validation selection | Lowest validation MAE in seconds; test evaluated after selection |

These are the V2 input contract and configurable defaults. A final practical
node count and real-data metrics can only be selected after the dataset arrives.
Inspect the actual dataset before training; the CLI prints counts, selected node
IDs, split dates, coverage, feature order and shapes before optimization starts.

Targets never cross split boundaries. Validation and test windows may use earlier
observations as context, including the immediately preceding split. In rolling
evaluation, earlier validation/test measurements become available only after their
bins end, just as they would during inference. No backward fill is performed.
Segments with insufficient training coverage are excluded and reported.

This predicts segment traffic conditions. `eta_minutes` is the segment duration
divided by 60. It does not estimate waiting time, whole-route arrival, or remaining
travel time for a bus already partway through a segment. Predictions are clipped
at zero after inverse scaling. Check held-out MAE against the saved persistence
baseline before deciding whether the model is useful for passengers.

## Required real data

Provide a CSV with these columns and matching GTFS `trips.txt`, `routes.txt`,
`stops.txt`, and `stop_times.txt`:

```text
trip_id,from_stop_id,to_stop_id,departed_at,arrived_at
```

IDs must refer to consecutive stops of that GTFS trip. Timestamps must contain a
date and timezone offset. Each row must represent a measured completed traversal,
not a scheduled journey. Repeated trips on different dates are supported. Duplicate
records, missing timestamps, unknown trips and nonpositive durations are rejected.
The pipeline derives route IDs and travel seconds; it does not invent speed,
dwell, headway, distance or direction columns. Raw GPS fixes require a separately
validated stop departure/arrival extraction step before they satisfy this contract.

## Commands (from the project root)

```bash
.venv/bin/python -m pip install -r ml/travel_time/dcrnn_v2/requirements.txt

# These paths must contain actual observations and their matching GTFS.
.venv/bin/python -m ml.travel_time.dcrnn_v2.train \
  --observations datasets/raw/segment_traversals.csv \
  --gtfs datasets/gtfs --inspect

.venv/bin/python -m ml.travel_time.dcrnn_v2.train \
  --observations datasets/raw/segment_traversals.csv \
  --gtfs datasets/gtfs \
  --output ml/travel_time/dcrnn_v2/artifacts

# New process: load the bundle and reproduce its held-out raw-input sample.
.venv/bin/python -m ml.travel_time.dcrnn_v2.inference \
  --artifacts ml/travel_time/dcrnn_v2/artifacts --sample

# Regression/integration tests: temporary synthetic data only.
.venv/bin/python -m unittest ml.travel_time.dcrnn_v2.test_pipeline -v
```

An existing output directory is rejected to protect earlier runs. Use a new
directory for each experiment. A failed run may leave an incomplete bundle; it
cannot be loaded without a complete, verified manifest. Training is CPU-only,
seeded, uses deterministic PyTorch operations, and saves package versions.
`--data-kind synthetic` explicitly labels test fixtures; the default observed-data
mode rejects the repository's fictional GTFS feed.

## Reusable inference

```python
from ml.travel_time.dcrnn_v2.inference import predict_eta

prediction = predict_eta(
    "recent_completed_traversals.csv",
    as_of="2026-10-06T09:00:00+00:00",  # a completed-bin boundary
    route_id="your_actual_route_id",
    from_stop_id="your_actual_upstream_stop_id",
    to_stop_id="your_actual_downstream_stop_id",
    artifact_dir="ml/travel_time/dcrnn_v2/artifacts",
)
```

The returned dictionary contains `predicted_travel_time_seconds`, `eta_minutes`,
the segment identity, `horizon_seconds`, observed input coverage, the data kind,
and the prediction scope. A list of raw traversal dictionaries or a DataFrame
can also be passed. The predictor is cached per artifact path, runs in `eval()`
and `torch.no_grad()`, and strictly loads a V2 state dictionary. It rejects future
observations, unaligned cutoff times, insufficient history and unknown segments.

Provide the recent window plus each node's latest earlier observation to preserve
forward-fill history. Without an earlier measurement, the documented training
median is used. At least one trained node must have a recent measured bin;
individual nodes with missing measurements report their coverage as zero.

## Bundle saved by successful training

- `dcrnn_v2_best.pt`: model state, exact architecture config, feature order, best epoch and validation metrics.
- `model_config.json`, `training_config.json`, `feature_config.json`: complete model and processing contracts.
- `adjacency.npy`, `supports.npy`, `node_mapping.json`, `trip_topology.json`: exact graph and ID order.
- `scaler.json`: training means, standard deviations and fallback medians; no executable pickle.
- `prepared_arrays.npz`: time-indexed inputs, targets, masks, timestamps and split target indices.
- `observations.csv`, `gtfs/`: measured training source and the GTFS tables used for topology.
- `sample_observations.csv`, `sample_expected.json`: raw held-out sample, cutoff, shapes, scaled and inverse-scaled reference predictions.
- `metrics.json`, `training_history.json`, `data_report.json`: test/validation MAE, RMSE, R², WAPE and persistence comparison, training history and dataset inventory.
- `source/`: source/config/dependency snapshot used to train the bundle.
- `manifest.json`: SHA-256 file hashes, schema version, data kind and runtime versions.

Inference checks every artifact's hash and verifies that the model/preprocessing
source matches the training snapshot. R² is null when target variance is zero;
WAPE is null when its denominator is zero. No metrics are manufactured for empty
splits: training rejects them.

The default artifact checkpoint is explicitly unignored in the root `.gitignore`.
Commit the entire bundle alongside this source to make a fresh checkout runnable.
Artifacts stored in custom output directories need an equivalent Git ignore
exception for their checkpoint. No Kaggle notebook or V1 artifact is needed.

## Source files

`graph.py` validates GTFS topology and constructs diffusion supports.
`preprocess.py` implements shared timestamp validation, binning, scaling and causal
feature generation. `dataset.py` constructs windows. `model.py` contains the
diffusion convolution, DCGRU cells, stacked encoder, autoregressive decoder and
output projection. `train.py` handles chronological training and exports the full
bundle. `inference.py` loads it once and predicts from raw observations.
`artifacts.py` implements the bundle integrity checks.
