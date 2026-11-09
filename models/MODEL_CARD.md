# SARScope frozen temporal model

This directory holds **model metadata**, not unverified weight files. The existing production loader is [`engine/model.py`](../engine/model.py), used from the inference worker [`backend/worker.py`](../backend/worker.py) via [`engine/pipeline.py`](../engine/pipeline.py).

- Input: Sentinel-1 VV/VH monthly radar data; georeferenced 256 × 256 pixel tiles at approximately 10 m per pixel.
- Outputs: nine Dynamic World-aligned land-cover labels plus raw softmax vectors. These are **predictions**, not ground-truth maps or calibrated probabilities of correctness.
- Frozen checkpoint: `best.pt`, SHA-256 `a52e9f4f69d4647dfad7b6b01fb3613070f91201aa4dceb004db410f6b79b2b5`, selected using validation data at epoch 13.
- Held-out evaluation against weak labels: OA 74.17%, mIoU 42.39%. Do not translate these into independently measured accuracy.
- Generalization outside the 2021 training distribution has not been independently validated.

## Install the real trained model

The weights are **not available in the recovered source exports** and have not been fabricated. Obtain the original `SARScope_selected_restore.zip` from the authorized backup, then:

```bash
python scripts/model_assets.py import-archive --archive /absolute/path/SARScope_selected_restore.zip
python scripts/model_assets.py status
python local_tools.py smoke
```

The verified model is stored at `workspace/restored/sarscope-baseline-20261108/fp32_control_seed42/temporal/best.pt`, not committed to Git. `workspace` is ignored; the existing loader verifies SHA-256 and the prepared manifest before using the checkpoint. The restore includes the normalization statistics and prepared-data manifest required for inference. The full prepared dataset is a separate training artifact and is **not required for inference**.

For hosted delivery, place an authorized copy of the restore bundle in private artifact storage and use `scripts/model_assets.py download` with an HTTPS URL and optional Bearer token. See [`docs/data-and-model.md`](../docs/data-and-model.md).
