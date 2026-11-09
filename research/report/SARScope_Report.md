# SARScope: retrospective land-cover analysis from Sentinel-1

Author: Keyur Chaudhari · SRH Hochschule Heidelberg · Deep Learning

## Objective and scope

SARScope accepts a location and a historical start month, retrieves twelve monthly Sentinel-1 composites, produces nine-class land-cover maps, and calculates area shares and predicted changes. The prototype covers one 256 × 256 pixel tile (2.56 × 2.56 km at 10 m). It is a research prototype with substantial class-specific errors, not a validated operational land-use change detector.

## Dataset and preprocessing

The baseline contains 1,300 chips from 52 geographic regions for January–December 2021. Whole regions were assigned to 925 training chips, 200 validation chips and 175 test chips. The preserved metadata lists the regions below. Spatial screening and source hashes are retained in the prepared-data manifest and original audit records.

- train: 925 chips, 37 regions: ahmedabad_in, baragan_ro, beauce_fr, bernese_alps_ch, cambridge_uk, dhaka_bd, flevoland_nl, griffith_au, guangzhou_cn, imperial_valley_us, iowa_us, johannesburg_za, lagos_ng, lucknow_in, manaus_br, mekong_vn, mexico_city_mx, munich_de, munster_de, niamey_ne, nile_delta_eg, north_china_plain, pekanbaru_id, pergamino_ar, phoenix_us, po_valley_it, poltava_ua, regina_ca, tadla_ma, tampere_fi, thessaly_gr, toshka_eg, trondheim_no, ulaanbaatar_mn, valencia_es, warsaw_pl, western_desert_eg.
- val: 200 chips, 8 regions: fresno_us, great_plain_hu, kanto_jp, khumbu_np, okavango_bw, paris_fr, riyadh_sa, sundarbans_bd.
- test: 175 chips, 7 regions: dalarna_se, east_oweinat_eg, leipzig_de, ludhiana_in, nairobi_ke, seville_es, sorriso_br.

Sentinel-1 source: COPERNICUS/S1_GRD_FLOAT, IW mode with VV and VH. Earth Engine supplies calibrated linear radar backscatter with upstream noise/orbit/geometric terrain processing. The inherited processing applies angular volume-model radiometric terrain flattening using the Copernicus DEM, masks layover/shadow and incidence angles outside 31–45°, and takes monthly means in linear power. Both orbit directions are included, matching the training recipe. Locally, the frozen Lee-style 5 × 5 filter uses the inherited ENL × observation-count approximation, then converts to decibels. This heuristic is a limitation, not a newly validated noise model.

Each patch stays on its fixed 10 m UTM grid. Missing or nonpositive backscatter remains invalid; no missing pixel is silently assigned a land-cover class. The data are normalized using training-only means and standard deviations. No geometric data augmentation was used in the reference training implementation; training batches were shuffled with a seeded generator. The reference implementation is included for exact reproducibility.

Dynamic World provides weak labels from the argmax of mean monthly class probabilities, aligned to the same grid and month. A pixel is scored only where both valid SAR input and a valid label exist. Optical labels are supervision, not model features. The nine classes are: water, trees, grass, flooded_vegetation, crops, shrub_and_scrub, built, bare, snow_and_ice. Class distribution/support evidence is saved in dataset_audit_evidence.json and the split metric JSON files; class imbalance is material.

| Class | Training scored pixels | Training share | Validation share |
|---|---:|---:|---:|
| water | 39,732,632 | 6.59% | 5.86% |
| trees | 80,607,562 | 13.37% | 19.74% |
| grass | 23,474,225 | 3.89% | 5.50% |
| flooded_vegetation | 2,150,173 | 0.36% | 1.56% |
| crops | 224,277,256 | 37.21% | 21.19% |
| shrub_and_scrub | 27,170,752 | 4.51% | 8.90% |
| built | 95,575,729 | 15.86% | 20.64% |
| bare | 72,389,706 | 12.01% | 15.41% |
| snow_and_ice | 37,302,932 | 6.19% | 1.21% |


Counts refer to scored pixel-months, so the same ground pixel can contribute in several months. No additional confidence threshold was applied to the baseline labels.

## Model and training

The reference model is U-Net with a ResNet34 encoder initialized with ImageNet weights during training. Its eight channels are VV, VH, VV−VH, twelve-month VV mean, VH mean, VV standard deviation, VH standard deviation, and a valid-input mask. The annual statistics supply temporal context; this is not a recurrent network or a temporal-attention model. Because future months in the requested window contribute to the context, inference is retrospective.

Training used AdamW, initial learning rate 0.0003, weight decay 0.0001, batch size 8, cosine learning-rate decay, 30 epochs and seed 42. The objective was unweighted cross entropy on valid labels. The final reference used FP32 training/evaluation with TF32 and automatic mixed precision disabled after earlier FP16 overflow was investigated. Completed work is retained rather than retrained for the submission. Training curves are included in evaluation/training_curves.png.

The retained checkpoint is the seed-42 unweighted FP32 control at epoch 13, selected using validation mIoU. It scored validation OA 62.57% and mIoU 36.40%. The model selection is frozen before the submission script opens the test labels. The script verifies checkpoint/data identity and replays the validation confusion matrix first.

## Experimental results

Held-out test status: evaluated with the fixed checkpoint; OA 74.17%, mIoU 42.39%.

| Class | Validation IoU | Validation F1 | Test IoU | Test F1 |
|---|---:|---:|---:|---:|
| water | 81.84% | 90.02% | 30.55% | 46.81% |
| trees | 52.60% | 68.94% | 62.36% | 76.82% |
| grass | 13.59% | 23.93% | 12.84% | 22.77% |
| flooded_vegetation | 0.04% | 0.09% | 0.00% | 0.01% |
| crops | 52.76% | 69.07% | 63.59% | 77.74% |
| shrub_and_scrub | 24.84% | 39.80% | 18.01% | 30.52% |
| built | 69.69% | 82.14% | 72.46% | 84.03% |
| bare | 28.23% | 44.03% | 73.89% | 84.98% |
| snow_and_ice | 4.01% | 7.72% | 47.78% | 64.67% |


IoU = TP/(TP+FP+FN), F1 = 2TP/(2TP+FP+FN), OA = all correct scored pixels/all scored pixels. Mean IoU averages defined class IoUs. A class absent from both reference and predictions is undefined and omitted; a false-positive-only class has zero IoU. These scores measure agreement with Dynamic World weak labels. Per-region and per-month results are supplied in the evaluation JSON, so global averages do not conceal every regional failure.

The class-balanced experiment used three paired seeds (42, 123, 2026). Mean validation mIoU was 36.446% for unweighted controls and 36.706% for weighted models. The paired improvement was +0.260 percentage points with sample SD 1.129; only 1/3 pairs improved. Mean OA changed by -2.198 percentage points. This is inconclusive descriptive evidence, not a statistically established improvement. The weighted variant was not promoted.

## Prototype architecture and accounting

Inputs → fixed UTM grid and monthly windows → Earth Engine Sentinel-1 retrieval → verified monthly cache → frozen SAR preprocessing → frozen FP32 model → twelve georeferenced maps → area/change tables → notebook/Streamlit/offline report.

Monthly class percentages use the full fixed AOI, with an explicit unobserved category; observed-only percentages are also exported. Areas use projected 100 m² pixels rather than geodesic area. Consecutive-month and first-to-last changes use the intersection of valid observations in the two compared months. For each class, change in percentage points equals its later common-support percentage minus its earlier common-support percentage. A pair without common support has null changes, not zero. A transition matrix records both directions of class transitions, since net area change can hide opposing transitions.

Softmax entropy is saved as uncalibrated model ambiguity. It is not a verified error probability, and there is no unsupported confidence-threshold guarantee.

## Case study and external map comparison


### 49.4875, 8.4660 — 2021-01

Inference complete: True; external comparison status: COMPLETE. Annual WorldCover agreement: OA 80.94%, mIoU 26.30%, comparable area 99.64%. Monthly maps, monthly_shares.csv, changes.csv, transitions.json, GeoTIFFs and the offline case_report.html are provided in cases/4c50a61fa03e274d/.

The default case is Mannheim, latitude 49.4875, longitude 8.4660, January–December 2021. ESA WorldCover 2021 v200 is never used as an inference feature or training target in this pipeline. For the annual sanity check, the model's unique modal class over all twelve observed months is compared with a documented broad class crosswalk. Missing reference pixels, mangrove and moss/lichen classes, temporal ties and incomplete annual prediction support are excluded. Herbaceous wetland and flooded vegetation are not identical categories. The comparison is external-map agreement, not surveyed ground truth; shared satellite inputs and map errors limit independence. An annual map cannot validate month-specific changes.

## Mannheim error analysis

On the common annual support, built occupies 88.91% of the predictions versus 72.43% of the WorldCover reference; trees occupy 1.62% versus 13.56%. The high overall agreement is dominated by built-up land and coexists with mIoU of only 26.30%. The case is technically complete but does not establish operational reliability. January-to-December predicted changed-pixel fraction is 1.857%; no independent monthly change reference was evaluated.

## Critical discussion

Validation performance is uneven: water and built areas are stronger than flooded vegetation, snow/ice and grass. Radar backscatter responds to moisture, roughness, geometry and vegetation structure; different classes can look similar. New locations may differ from the training regions in climate, land cover, orbit geometry or acquisition coverage. Seasonal crops, wet soil and snow can produce plausible apparent changes without permanent land-use conversion. Mixing orbit directions can introduce additional variation. Annual context couples the monthly predictions and limits real-time use.

Classification errors at either date can inflate changed-pixel percentages. A visually smooth map or a high maximum softmax probability does not prove a correct class. Further work should investigate stronger supervision, orbit handling, class-specific failures, calibration and replicated improvements. The separate probability-target export is ongoing research and is not a prerequisite or a claimed result of this submission.

## Reproducibility and deliverables

Dataset identity: `6c3b62d7d71f22d4d098b9fbaf497daf45fe5c3c4e2198fa62cb1db17c4662cf`. The checkpoint remains at restored/sarscope-baseline-20261108/fp32_control_seed42/temporal/best.pt; exact SHA-256 is recorded in the evaluation protocol and each case's model identity. Original backups, prepared arrays, source code, training history, environment lock, comparison reports, executed results notebook and case exports are preserved. This report is generated from actual saved outputs; pending stages are explicitly marked.

Before submission, attach the report PDF, code archive, trained checkpoint or accessible download link, dataset or accessible download link, executed notebooks, and a screen recording showing input → monthly predictions → percentages/changes → limitations. Verify that the assessor can access large-file links. The compact review ZIP deliberately excludes model weights and dataset arrays.

## Source documentation

- Sentinel-1 GRD_FLOAT: https://developers.google.com/earth-engine/guides/sentinel1
- Dynamic World V1: https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1
- ESA WorldCover v200: https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200
- Earth Engine computePixels: https://developers.google.com/earth-engine/apidocs/ee-data-computepixels

Generated: 2026-11-09T10:53:55.926112+00:00
