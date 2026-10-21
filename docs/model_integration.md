# Model integration

## Compatibility audit

The existing crowd checkpoint was inspected on CPU with `torch.load(..., weights_only=True)`. Its dictionary contains `model_state_dict`, configuration and training metadata. Supporting artifacts include the 10-stop mapping, adjacency, scaler CSV, prepared arrays and feature contract. Inputs are boarding, landing, previous estimated loader, cyclical hour/day values and weekend flag. The archived architecture implementation is absent from this checkout's crowd source files, and these measured/count features do not match the new seven-stop ratio targets. No tensor truncation, guessed mapping or random features are passed to it. Tensor shapes and checkpoint configuration are recorded in `ml/synthetic/original_artifact_inspection.json`.

The actual saved historical DCRNN artifact is nine segments, six features, 12 input bins, hidden size 16, two DCGRU layers and diffusion order 2. This differs from the expected configuration in the request; the saved artifact is authoritative. Its original inference CLI verifies source hashes, feature contract, node mapping, forward/backward transitions, scaling and saved predictions. The historical reference was reproduced during verification and remains separately exposed at `/api/models/historical-demo`.

Archived metrics: the crowd CSV reports MAE 2.53414 and RMSE 4.80720 in original loader units; the DCRNN bundle reports test MAE 6.75178 seconds versus persistence 9.62308 seconds on its historical dataset. These are original experiments, not new synthetic-network scores.

## New synthetic-network models

ST-GCN is a new reproducible implementation in `ml/synthetic/models.py`: two gated temporal-convolution → normalized graph-convolution → temporal-convolution blocks, hidden dimension 32, temporal kernel 3, followed by a residual occupancy head. Inputs are `[batch,12,7,8]`; output is `[batch,7]`. The eight explicitly ordered features are boarding_ratio, alighting_ratio, occupancy_ratio, hour_sin, hour_cos, dow_sin, dow_cos and is_weekend. Only the first three are standardized per stop. Graph edges connect consecutive stops in either direction, with self-loops and symmetric degree normalization.

DCRNN reuses the existing V2 DCGRU implementation with a new 18-segment graph, four historical 15-minute bins, four features, hidden dimension 16, two layers, diffusion order 2, and a one-bin horizon. Directed nodes are `(route_id,from_stop,to_stop)`. Forward transitions normalize adjacency plus self-loops; backward transitions independently normalize its transpose. Features are travel_minutes_z, observed, hour_sin and hour_cos. Only travel minutes are standardized. Output is inverse-scaled to minutes per segment.

Models train on CPU for 18 epochs with fixed Python/NumPy/Torch seed 42, Adam, L1 loss and gradient clipping. Validation days select the checkpoint; test days are evaluated after selection. The manifest records held-out MAE, RMSE and persistence MAE, exact train/validation/test counts, scaler arrays, graph/node/feature contracts, file hashes, training source hashes and GTFS hashes. Never use an occupancy-ratio metric as an error in passenger counts.

The runtime checks version, hashes, required files, node order, feature names, scaler dimensions/finiteness/positive scales, replay dimensions, normalized DCRNN supports and strict checkpoint parameter compatibility. CPU `weights_only=True` loads both new state dictionaries. Predictions are finite-checked and clipped to valid physical bounds. If artifacts/dependencies/validation fail, the response is explicitly `BASELINE_FALLBACK` with the reason and baseline model names. `BUSSURE_DISABLE_MODELS=1` tests this path. Original baseline API results remain independent.

## Prediction interpretation

`/api/predict/eta` returns next-bin segment durations, optionally summed for a selected route before disruption adjustments. `/api/predict/crowd` returns stop occupancy ratio with LOW <0.4, MEDIUM from 0.4 to below 0.7, HIGH >=0.7. These are documented synthetic ratio thresholds, unlike the original model's count-based per-stop terciles. Journey crowd uses the highest predicted stop occupancy encountered as a conservative route proxy, not a bus sensor reading. It can tie between routes serving the same stops.

The integrated planner adds scenario effects, remaining GPS segment fraction, timetable waiting, walking and 30-second dwell assumptions. It reports prediction mode, history source, forecast horizons, explanations and deterministic scenario ranges. Live GPS does not turn a replay crowd forecast into a real-time crowd observation.

## Reproduce

```sh
.venv/bin/python -m pip install -r ml/synthetic/requirements.txt
.venv/bin/python scripts/generate_synthetic.py
.venv/bin/python -B -m ml.synthetic.train --epochs 18
.venv/bin/python -B -m unittest ml.synthetic.test_retraining -v
```

Restart the backend after training or regenerating. The slower retraining test trains twice for one epoch in temporary directories and checks identical learned weights and metrics; it does not overwrite the 18-epoch application models. Training source changes intentionally invalidate old artifacts until retraining.


## Showcase evaluation dashboard

The portfolio extension adds `/api/models/evaluation`, which recomputes held-out actual/predicted/persistence series from the unchanged artifacts. Aggregate test MAE/RMSE match the manifest; charts sample 64 windows per selectable node while full metrics use every test window/node. This endpoint is evaluation, not runtime ground truth. See [showcase.md](showcase.md).
