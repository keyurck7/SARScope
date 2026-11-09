# Update SARScope Local and run a real location

## Replace the app files safely

1. Let any running analysis finish. Stop the local app with Ctrl+C in its terminal.
2. Download the current `SARScope_Local.zip` and extract it into `C:\SARPres`, merging with the existing `SARScope_Local` folder. Replace matching application files.
3. Keep `SARScope_Local\workspace`, `SARScope_Local\.venv` and all original backup archives. This update ZIP contains neither workspace nor environment, so a normal merge does not overwrite your checkpoints, credentials or results. Do not delete the old folder first.
4. Run `01_START.cmd` and refresh the browser with Ctrl+F5. The header should say `LOCAL / 02`.

If this is your first local installation, follow `START_HERE.md`. Run `02_ENABLE_INFERENCE.cmd` once to install CPU dependencies, verify/import the checkpoint and pass the runtime check; then `03_SIGN_IN.cmd` to authorize Earth Engine. An existing successful setup can be reused. No Node.js or university GPU is needed.

## Run Cairo with the existing validated input recipe

Open Local setup and refresh its status. The model, dependencies, credentials and CPU runtime check must all be ready.

Enter latitude `30.0444`, longitude `31.2357`, select **Choose historical period**, and set start month `2021-01`. Click **Analyze location**. This is one 2.56 km square tile centered on those coordinates, not the whole city.

The backend downloads missing Sentinel-1 months, verifies any cached months, applies the frozen preprocessing and runs the actual checkpoint on CPU. The displayed result changes to the new case only after it finishes. It does not generate a map by recoloring Mannheim. Failed jobs display the error and preserve completed downloads.

A new completed case opens in **Overlay** at 40% opacity. The underlying image is genuine processed VV SAR, not an optical image or generated texture. Use Radar to inspect the input display; Land cover to inspect the class raster; the legend to isolate classes. A transparent overlay cannot create roof boundaries that the model did not predict.

Check the request coordinates, all twelve months, observed coverage and acquisition provenance. Export the full case ZIP. That ZIP now also includes the radar underlays and request context. Keep a second copy off the computer.

## Analyze recent available imagery

Select **Latest completed 12 months**. On 9 November 2026, the request resolves to November 2025 through October 2026. The server resolves the window itself, even if the browser was left open overnight. Recheck the resolved window in the case after completion.

This means on-demand retrieval of available observations in twelve finished calendar months. It does not mean imagery captured right now, a current-month composite, or guaranteed complete provider ingestion. A checksum-verified cache is reused for repeated identical requests. The latest acquisition date and the download date are separate. Older cached receipts without acquisition timestamps show that field as unavailable.

The model was developed/evaluated on 2021 data. Other years are not separately validated. Keep this distinction in the submission. Historical 2021 is the first functional check; do not interpret a recent map as a newly validated model.

## What changed and what did not

- Added historical/latest-completed period selection, resolved by the backend.
- Added scene inventory count and acquisition/download timing where receipts provide it.
- Added explanation of dominant colours and annual WorldCover disagreement on comparable pixels.
- New cases default to a genuine radar overlay; the saved Mannheim sample still has no radar underlay.
- Re-running the same case refreshes its displayed result.
- Full case exports now include generated radar display layers.
- Added regression checks for calendar rollover, request routing, timestamp semantics and export contents.
- The checkpoint, model architecture, normalization, preprocessing, class palette, saved evaluation and original Mannheim map pixels are unchanged. The retrieval pipeline adds timestamp metadata only.

## Verification and remaining acceptance check

The updated package passed 19 backend tests and the TypeScript/Vite production build. Browser checks covered period selection, the date reverting correctly, December map navigation, source inventory and the annual reference-disagreement panel.

The authoring environment has no copy of your actual checkpoint or your Earth Engine credentials. Therefore authenticated Cairo retrieval, actual checkpoint CPU inference and Windows launcher execution have not been performed here. The worker-flow test uses explicit fixtures; it is not a real imagery run or accuracy test. Complete the real local run above before claiming end-to-end local deployment.

If it fails, retain the error and the latest files in `workspace\jobs`; do not share Earth Engine credentials or authorization codes.
