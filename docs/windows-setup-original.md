# SARScope Local — start here

A React + TypeScript map explorer, served by FastAPI on your own Windows computer. The downloaded package already includes the built interface: **you do not need Node.js, a university server, or GPU credits.**

The bundled Mannheim case contains real results from your completed run. New locations use your frozen model on **CPU**. Downloading new Sentinel-1 data still requires internet and your Google Earth Engine access. After retrieval, model inference runs locally. This is not a replacement for Earth Engine's data service.

For an existing installation, first follow [UPDATE_AND_RUN.md](UPDATE_AND_RUN.md) to preserve the environment and saved results. The imagery-window control now offers either a historical start month or the latest completed twelve months; see that guide for its limits.

## 1. Keep the backups and extract the app

Keep all 22 rescue archives, the records ZIP and verification report in `C:\SARPres`. Do not delete them.

Extract **SARScope_Local.zip** into `C:\SARPres`. The result should be:

```
C:\SARPres\SARScope_Local\01_START.cmd
C:\SARPres\SARScope_Local\02_ENABLE_INFERENCE.cmd
C:\SARPres\SARScope_Local\03_SIGN_IN.cmd
C:\SARPres\SARScope_selected_restore.zip
```

The selected restore ZIP is the ~5.15 GiB file you already made with `SARScope_Restore\restore.py pack`. It is not included in this small UI download. If you only have the 22 original rescue ZIPs, reuse your existing restore pack command before step 3; do not rename a rescue part to the selected bundle name.

## 2. Open the interface

Use **64-bit Python 3.12**. In PowerShell, check:

```powershell
py -3.12 --version
```

If it is missing, install Python 3.12 (Windows 64-bit) from the official Python website, then reopen PowerShell. Python 3.12.10 has a Windows installer: https://www.python.org/downloads/release/python-31210/

Double-click **01_START.cmd**. The first run creates a private `.venv` and installs the viewer dependencies. Keep its terminal open. Your browser opens:

**http://127.0.0.1:8765**

You can immediately explore Mannheim's real January–December 2021 maps, colour legend, region labels, monthly composition and evidence page. CPU inference is disabled until the next steps pass. No package install is needed on subsequent viewer launches unless you remove `.venv`.

Equivalent PowerShell commands:

```powershell
cd C:\SARPres\SARScope_Local
.\01_START.cmd
```

## 3. Enable CPU inference once

In a second PowerShell window:

```powershell
cd C:\SARPres\SARScope_Local
.\02_ENABLE_INFERENCE.cmd
```

This does four things:

1. Installs pinned CPU PyTorch 2.9.0, torchvision 0.24.0 and the inference dependencies.
2. Reads your existing selected restore ZIP and extracts **only the checkpoint, training statistics and dataset manifest** into `workspace\restored`. It does not unpack all training arrays or alter the original backup.
3. Verifies the imported checkpoint against its fixed SHA-256, and verifies the normalization statistics and manifest against the frozen dataset identity.
4. Loads your actual checkpoint and runs a **synthetic-input runtime check** on CPU. It checks shapes and finite probabilities. Synthetic input is never displayed as a real location, and this check is not an accuracy measurement.

Wait for **Inference setup complete**. The first setup downloads substantial packages; runtime varies with connection and CPU. Reserve several GB of free space for the environment, checkpoint and new case caches. An 8 GB laptop may work, but 16 GB RAM is preferable; your hardware has not been measured here.

If the backup ZIP is elsewhere:

```powershell
.\02_ENABLE_INFERENCE.cmd --bundle "D:\Backups\SARScope_selected_restore.zip"
```

If setup stops, retain the error and `workspace\cpu_runtime_check.json` if generated. Do not change weights or bypass checksum checks. You can continue viewing the saved Mannheim case.

## 4. Sign in to Earth Engine locally

```powershell
.\03_SIGN_IN.cmd
```

Complete the Google sign-in in your own browser, using the account previously authorized for Earth Engine. The script checks the existing project `gae-application-308005`. Credentials stay in your local Earth Engine configuration; they are not included in case exports.

For a different authorized project:

```powershell
.\03_SIGN_IN.cmd --project YOUR_PROJECT_ID
```

Set that same project in **Local setup** in the UI. A project-not-registered or permission error must be resolved in Earth Engine; changing coordinates will not fix it.

## 5. Run Cairo

In the UI, open **Local setup → Refresh setup status**, then return to the explorer.

Use:

| Field | Value |
|---|---|
| Latitude | `30.0444` |
| Longitude | `31.2357` |
| Start month | `2021-01` |

Choose **Analyze location**. The system retrieves twelve monthly Sentinel-1 composites, applies the frozen preprocessing, runs the trained model on CPU and saves the maps. Progress appears above the explorer. Only one analysis runs at a time. A failed retrieval can reuse completed verified monthly downloads when you retry the same request.

Keep the terminal open, the laptop plugged in and Windows awake until the job completes. CPU processing will generally be slower than the A6000 run; there is no measured completion estimate for your laptop. The app does not train a new model or access the held-out test labels.

The displayed tile is **2.56 × 2.56 km centered on the coordinates**, not all of Cairo. It uses a 10 m grid. Choose other coordinates for other tiles; mosaicking a whole city is not included.

## 6. Explore and export

- **Land cover:** colour-coded model classes.
- **Overlay:** real processed monthly VV radar underlay with adjustable class-colour opacity, available for newly completed local cases.
- **Radar:** terrain-corrected monthly VV composite after the frozen filter, displayed at a fixed −30 to +5 dB range. This display contrast does not alter the model inputs.
- **Region labels:** leaders anchor inside the largest connected predicted regions. They are class annotations, not object detections. Tiny regions may have no callout but remain visible in the legend and pixel inspector.
- **Class legend:** click a class to isolate it. Click again to show all classes.
- **Months:** choose a month or play the timeline. **First ↔ selected** compares the first month with the selected month. Drag the comparison slider.
- **Pixel inspector:** hover or tap inside the map. It reports the predicted class of a 10 × 10 m cell. In comparison mode it respects the side being inspected.
- **Exports:** download class-area CSV, predicted-change CSV, selected map or the full case ZIP for new local runs. Open the case report and print to PDF if desired.

Mannheim's imported review has no radar data or GeoTIFFs. Its Radar/Overlay controls are intentionally unavailable. Rerun Mannheim after enabling inference to create the real radar underlay and georeferenced exports; no synthetic background is substituted.

## 7. Preserve your work and prepare submission

New outputs are saved under:

```
C:\SARPres\SARScope_Local\workspace\submission_v1\cases\<case-id>\
```

This includes `case_report.html`, `case_export.zip`, twelve class GeoTIFFs, class maps, actual radar display maps, class areas, change tables, model identity, acquisition receipts, and raw/prediction caches. Logs and progress are in `workspace\jobs`. Checkpoint assets are in `workspace\restored`.

Back up the **workspace** folder to another drive after successful runs. Keep your existing original rescue archives too. Exports intentionally exclude authentication credentials. The full app folder contains the Python environment, so do not submit it blindly; use source code + README + required model/data delivery + exported results as specified by your rubric.

For a short demo: open Mannheim, show month navigation and class isolation, open Model evidence, then show Cairo only after a real completed run. Record locally. Do not describe the UI upgrade as an improvement in model accuracy.

## Troubleshooting

| Symptom | Action |
|---|---|
| `py` or Python 3.12 missing | Install official 64-bit Python 3.12, including the Python launcher, and reopen PowerShell. |
| Browser does not open | Leave the terminal running and open `http://127.0.0.1:8765` manually. |
| Port already in use | Reuse the already-open app; close the duplicate terminal. If needed, stop the original app with Ctrl+C after its job finishes. |
| Analyze button disabled | Complete steps 3–4, then refresh Local setup status. All runtime/asset/auth prerequisites must be present. |
| Wrong bundle/checksum | Use the verified selected restore ZIP. Do not edit or rename model files to force acceptance. |
| Interrupted install | Rerun the same setup command. Existing packages are reused. |
| Earth Engine authorization expired | Run `03_SIGN_IN.cmd` again. Never share credentials or authorization codes. |
| Out of memory | Close heavy applications and retry; CPU inference uses one month per batch and at most four threads. |
| WorldCover reference failed | If inference completed, maps remain saved. The report marks reference comparison unavailable/partial. |
| No data in a requested window | Choose a supported location/window. The system will not substitute invented imagery. |

## Scope and honest interpretation

This is a research prototype with nine broad classes: water, trees, grass, flooded vegetation, crops, shrub/scrub, built-up land, bare ground, snow/ice. It does **not** distinguish railway tracks, road types, individual buildings or detailed building boundaries like the high-resolution examples. Colours and callouts explain the existing predictions; they do not create new model capabilities.

Saved test mIoU is **42.39%** and overall agreement **74.17%** against Dynamic World weak labels. Class performance varies substantially. Those are previous server results, not a Cairo or CPU accuracy claim. CPU and GPU computations may differ numerically; exact bitwise equality is not promised. Coverage measures data availability, not confidence. Twelve-month context means retrospective analysis. Apparent changes can arise from seasonal variation or classification error.

## Developer commands

The production browser bundle is included in `frontend\dist`. To modify React, install a supported Node.js version and run `npm ci`, then `npm run build` inside `frontend`; restart/reload the local app. `npm run dev:frontend` starts a frontend-only Vite development server; use the built bundle with `serve.py` for the fully integrated local app. The `dev` script is a read-only preview harness.

Backend regression tests (inside the local environment):

```powershell
.\.venv\Scripts\python.exe -m pip install httpx
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_local.py -v
```

Official setup references:
- https://pytorch.org/get-started/previous-versions/
- https://developers.google.com/earth-engine/guides/auth
- https://www.python.org/downloads/release/python-31210/
