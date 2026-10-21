# SUNT cloud training setup

No cloud job has been submitted. The Mac development experiment is complete;
full-network preprocessing/training needs a separate size review before launch.

## Runnable Colab/Kaggle setup for the existing connected subset

Upload/mount the BusSure `ml/travel_time/dcrnn_v2` source and the small
`sunt_connected_subset/` directory. This requires about 1.3 MB of derived data,
not the 8.69 GB SUNT ZIP. A fresh inference-only run needs just the 1.67 MB
`sunt_dev_artifacts/` bundle plus source/dependencies. Do not unzip SUNT again.

From the project root in a terminal or notebook cell:

```bash
python -m pip install -r ml/travel_time/dcrnn_v2/sunt_requirements.txt
python -m ml.travel_time.dcrnn_v2.train \
  --observations ml/travel_time/dcrnn_v2/sunt_connected_subset/segment_traversals.csv \
  --gtfs ml/travel_time/dcrnn_v2/sunt_connected_subset/gtfs \
  --config ml/travel_time/dcrnn_v2/sunt_dev_config.json --inspect
python -m ml.travel_time.dcrnn_v2.sunt_experiment \
  --subset ml/travel_time/dcrnn_v2/sunt_connected_subset \
  --output ml/travel_time/dcrnn_v2/cloud_dev_artifacts
python -m ml.travel_time.dcrnn_v2.inference \
  --artifacts ml/travel_time/dcrnn_v2/cloud_dev_artifacts --sample
```

The existing V2 trainer is CPU-only. Selecting a cloud GPU runtime alone does not
move this model to the GPU. No GPU-support rewrite was made for this task.
PyTorch wheel/dependency installation space on Linux can be much larger than on
the Mac; use the runtime's provisioned packages where compatible and record exact
versions. CPU floating-point outputs may vary slightly across platform versions.

## Required gate for a larger SUNT experiment

1. Mount the already-extracted source read-only in cloud storage, or attach the
   provider's existing dataset. Do not create a second full local Mac copy.
2. Keep Parquet column projection and daily batches. Validate route/service/GTFS
   correspondence per day. Export route/date partitions incrementally, not one
   whole-network DataFrame. Keep training-derived node selection separate from
   validation/test labels.
3. Measure real row counts, usable target coverage, node count `N` and bins `T`
   before selecting a high-RAM runtime. Current Mac adapter intentionally caps
   requests at 14 days, 32 segments and 100,000 retained records/day.
4. Dense raw adjacency plus two supports alone need roughly `12*N*N` bytes of
   float32 storage. The feature timeline alone needs `24*T*N` bytes; masks,
   targets, temporary pandas objects and autograd add substantially more. For
   illustration only, 10,000 nodes and a year of 5-minute bins require about
   25.2 GB just for the six-feature timeline, plus about 1.2 GB for graph arrays.
   The actual full-network segment count has not been established.
5. Full-network work may need sharded/memory-mapped time arrays, streaming scaler
   fitting and sparse diffusion supports. Those changes require a reviewed
   integration with the existing V2 model; they were not silently introduced here.
6. **Stop and report the concrete data scope, RAM/disk estimate, target quality,
   runtime and training configuration before launching the larger job.** There is
   deliberately no unbounded full-network command or automatic cloud upload.

The supplied runnable setup reproduces the bounded experiment. It does not claim
that the current compact-data trainer is ready to ingest all 9.47 GB of SUNT.
