# Why the map looks different from the paper

SARScope predicts broad land cover. Red denotes built-up/impervious land, not an individual building footprint. The present model cannot distinguish railway tracks, road types or individual rooftops because those are not its output classes.

The cited paper uses 0.5 m SAR/optical imagery, manually added building/vegetation semantics for SpaceNet6, and DeepLabv3+ with fusion/translation branches. Its comparison is not a direct benchmark against SARScope. SpaceNet's released Rotterdam imagery is a regional research dataset, not a worldwide on-demand 0.5 m imagery service.

## Three different quantities

| Quantity | Current system | What changing it achieves |
|---|---|---|
| Area covered | 2.56 × 2.56 km | A larger area covers more geography; it does not reveal smaller objects. Larger areas would require tested tiling/mosaicking. |
| Output grid | 256 × 256 cells at 10 m spacing | Upsampling creates more display pixels, not new observations. |
| Sensor/product detail | Sentinel-1 IW GRD, approximately 20 × 22 m spatial resolution | Building-scale delineation needs genuinely finer imagery and suitable training labels. |

For intuition, a 20 × 20 m roof spans only 2 × 2 grid cells at 10 m spacing, with the effective SAR resolution coarser still. At 0.5 m spacing it spans 40 × 40 cells. Display enlargement cannot supply the missing measurements.

## The observed red dominance is not just styling

The saved Mannheim annual comparison used 65,303 common supported pixels. On those pixels:

| Cover | SARScope annual prediction | WorldCover 2021 reference |
|---|---:|---:|
| Built-up | 88.91% | 72.43% |
| Trees | 1.62% | 13.56% |

This suggests substantial built-up overprediction/tree underprediction relative to that reference. WorldCover itself has errors and is not independent surveyed truth. The disagreement does not by itself identify whether weak labels, geographic distribution, preprocessing choices or model capacity dominate the error. A separate input/label audit and controlled validation are needed.

Overlaying translucent class colours on the radar helps people inspect results. It does not improve classification accuracy. Keep the original predicted labels in exports. Do not add artificial roads, roofs, reference-derived boundaries or translated optical detail and present them as SAR detections.

## Practical order of work

1. Finish and record one genuine local coordinate-to-result run, including source dates, model identity and outputs. Preserve the completed submission model and its existing evaluation.
2. Use a fixed set of urban validation cases to inspect band order, physical units, masks, training statistics and the matching training/inference recipe. Audit how weak labels treat urban vegetation. Do not change the model based on the already-opened test set.
3. If the goal remains nine-class land cover, test clearly motivated changes on validation data and repeat across seeds. A different architecture or more epochs is not guaranteed to improve geographic generalization.
4. If the goal changes to roof/road segmentation, establish a separate experiment with high-resolution imagery, fine annotations, geographic holdouts and sufficient training compute. Start with a suitable high-resolution baseline before adding fusion or image translation. An off-the-shelf high-resolution checkpoint must match its sensor/channels/labels; it cannot be dropped into the current Sentinel-1 pipeline.
5. Assess pixel IoU and, for building footprints, object-level detection/boundary quality. Compare competing models on the same task, data and split. No model-superiority claim is currently supported.

Given the deadline and exhausted GPU credits, steps 1–2 protect the submission. A high-resolution experiment is additional research, not an overnight guaranteed replacement. The updated UI makes the existing model usable; it does not claim paper-level building segmentation.

## Primary sources

- Xu et al., Enhanced semantic segmentation in remote sensing images with SAR-optical image fusion (IF) and image translation (IT): https://www.nature.com/articles/s41598-025-19402-y (methods and experiments; PDF: https://www.nature.com/articles/s41598-025-19402-y.pdf).
- Copernicus SentiWiki, Sentinel-1 product specifications: https://sentiwiki.copernicus.eu/web/s1-products (IW GRD high-resolution product, 10 × 10 m pixel spacing and approximately 20 × 22 m spatial resolution).
- SpaceNet 6 official dataset description: https://spacenet.ai/sn6-challenge/ (half-metre data and building annotations over Rotterdam; expanded release acquisition details).
