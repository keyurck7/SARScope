# SARScope | Phase 2 quality and reproducibility checkpoint

Date: 9 November 2026. This is an **additive, model-frozen increment** based on the three exported cases and the latest local application archive. It is not a new trained model or a new scientifically validated segmentation system.

## Open immediately

- **SARScope_Quality_Review.html** (included at the app root): self-contained, offline interactive audit of Cairo, Mauritania and Queens. No Earth Engine connection, backend, Python, login, or npm install required. Select a site, change the month, and adjust prediction opacity to see the **saved** radar and class maps.
- **SARScope_Quality_Review_Preview.png**: inspected example of the October 2026 Mauritania warning state.
- **QUALITY_RULES_AND_RESULTS.json**: computed scene-count and review-rule summary, including unchanged source archive hashes.
- **SARScope_Local/**: local FastAPI + React application with all three saved case exports incorporated alongside the previously supplied Mannheim case. Run `01_START.cmd` on Windows after following `START_HERE.md`.

## Verified source changes

1. `backend/quality.py` computes per-month descriptive review fields and explicit warnings from saved scene receipts, predicted area shares and coverage.
2. `backend/data.py` attaches review fields to every API month. It does not alter model classes, model weights, predictions, acquisitions, or class percentages.
3. `backend/server.py` adds the three saved case folders as read-only review cases, without requiring Earth Engine to browse.
4. `frontend/src/main.tsx` and `frontend/src/style.css` contain an inline per-month quality panel. **The existing bundled frontend/dist still reflects the previously built interface**: to activate the new in-app panel, run `npm ci && npm run build` in `frontend/` on a machine with Node.js and network access. The offline quality dashboard contains the review immediately and needs no compilation.
5. `tests/test_quality.py` adds rule-level regression tests. The existing local suite also passes.

## Measurement definitions and cautions

- `source_scene_count` is the number of Sentinel-1 source scenes intersecting the tile according to the exported acquisition receipt. It is **not** a per-pixel count or certified data quality.
- `coverage_percent` is the proportion of pixels assigned model labels; 100% coverage does **not** mean 100% accuracy.
- Normalized entropy is uncalibrated predictive dispersion (0–1), **not** probability that the class is correct or incorrect.
- The threshold rules are intentionally visible review heuristics, **not** calibrated or externally validated alerts.
- Consecutive share changes use model predictions; they are **not** a verification of real-world changes.
- The fixed model was trained with 2021 radar and Dynamic World-derived weak references. The November 2025 to October 2026 cases have no independent matching-month ground truth in the exports.
- This is retrospective historical retrieval. A new request can fetch available imagery from Earth Engine (only after credentials, dependencies and checkpoint are configured), but it is not a live satellite transmission.

## Frozen original versus new review

The original saved ZIPs remain the source of truth: `case_export_Cairo.zip`, `case_export_Mauritania.zip`, and `case_export_Queens.zip`. Each is preserved byte-for-byte inside its corresponding `sample/cases/<id>/case_export.zip`. Their original SHA-256 values appear in `SAVED_CASES_PROVENANCE.json` and `QUALITY_RULES_AND_RESULTS.json`.

The checkpoint identity in all three source exports is:
`a52e9f4f69d4647dfad7b6b01fb3613070f91201aa4dceb004db410f6b79b2b5`

**The checkpoint bytes are not included in this package.** The existing local setup requires the separately prepared verified restore archive (`SARScope_selected_restore.zip`); do not rename a different file to bypass verification. The full prepared dataset is also not included in this package.

## Critical delivery checklist

Before an academic submission, ensure that the assessor can download and verify:

1. **Trained weights (`best.pt`)**, matched by SHA-256 to the checkpoint identity above; a server-internal path is not an assessor-accessible link.
2. **Prepared dataset** and a dataset manifest, or a stable authorized download link that was tested in an assessor-like account.
3. **Executed notebooks** including training/evaluation and visible output plots. The previous submission package has an executed results notebook, but ensure the complete course-required notebook scope.
4. **Report** with methodology, held-out test numbers (74.17% OA / 42.39% mIoU against Dynamic World weak labels), per-class limitations and clear evaluation protocol.
5. **Urban demo recording** actually opening the interface and producing/inspecting output, not just an animation of screenshots.
6. **Georeferenced results** (GeoTIFFs), original source receipts and a reproducible environment description.
7. **Submission audit** verifying upload sizes, archive integrity and access after upload. No file in the existing reviewed compact package alone fills the checkpoint/dataset gap.

Server paths reported by the previous handoff, **not verified to exist in this local container**, were:

```
~/vault/SARScope_Work/restored/sarscope-baseline-20261108/fp32_control_seed42/temporal/best.pt
~/vault/SARScope_Work/restored/sarscope-baseline-20261108/prepared/
```

On that server, calculate `sha256sum` and `du -sh` on the checkpoint and prepared dataset before transferring. Confirm the recipient is authorized to access the data. Never transfer Earth Engine tokens or `.config/earthengine/credentials` with deliverables.

## What is tested here

- Python local application/unit tests: **23/23 passing**.
- API loading for four saved cases (Mannheim plus Cairo, Mauritania, Queens): **4/4 returned valid JSON with 12 months and quality fields**.
- Standalone HTML in headless Chromium: **3 case selectors, 12 selectable months, Mauritania October warnings and Queens February limited-scene warning**, with no JS page errors.
- Source exports: previously checked georeferenced outputs, class accounting and transitions (the earlier audit is separate).

## What remains untested

- A fresh Sentinel-1 download or inference run from a new request on your Windows machine.
- Rebuilding the TypeScript React frontend in this environment: npm registry dependencies were unavailable, so the shipped `frontend/dist` is not updated with the new React quality panel.
- Accuracy of geographic labels for 2025–2026 from independently collected reference data.
- Reproduction of training from the full dataset or direct byte-level checkpoint verification here, because these large assets were not available in the inspected archive.

## Next scientific branch, without test leakage

Prioritize a stratified, independent reference study for the desert and urban outputs; produce confusion slices, class-specific independent accuracy estimates, and time-pair change reviews. Select future model improvements on a held-out validation plan, not by optimizing against the already examined test cases. Increase AOI by tiled inference, not upsampled pseudo-resolution.
