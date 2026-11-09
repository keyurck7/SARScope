# Model and dataset access

## Files included in Git

Tracked: Python source, inference loader, React source, compiled offline viewer, four saved case examples (Mannheim plus Cairo, Queens, Mauritania), georeferenced output examples, evaluation metadata, original research report and executed notebooks.

Excluded: the full training dataset, frozen weights, local output workspace, Google Earth Engine tokens, private credentials, CPU dependencies, and intermediate radar pixel arrays. **No actual `best.pt` was available in the supplied archives**, and no substitute model was generated.

## Install frozen inference assets

On a trusted machine with authorization to use the trained model:

1. Obtain the original `SARScope_selected_restore.zip` (not one of the small review or source ZIPs).
2. Install viewer dependencies, inference libraries, and the CPU PyTorch version described in the original Windows installer.
3. Run:

```bash
python scripts/model_assets.py import-archive --archive /path/to/SARScope_selected_restore.zip
python scripts/model_assets.py status
python local_tools.py smoke
```

The importer checks the archive's dataset and checkpoint identity, exact payload sizes, manifest, and SHA-256. The expected weight hash is in [`models/model-manifest.json`](../models/model-manifest.json). The checkpoint is stored in **`workspace/restored/`**, outside Git, and is verified again by the existing model loader at runtime.

## Remote artifact hosting

Use **private Hugging Face model/dataset repositories**, a private object store, or a private GitHub release if policy permits. Avoid committing a multi-gigabyte checkpoint/data bundle to ordinary Git. If the public model is explicitly authorized, publish a model card, licenses/data usage conditions and verified hashes alongside it.

The restore script can download from an accessible **HTTPS direct-download URL**:

```bash
export SARSCOPE_ASSET_TOKEN='YOUR_SHORT_LIVED_PRIVATE_TOKEN'
python scripts/model_assets.py download --url 'https://your-approved-storage.example/direct-file-url' --sha256 '<whole archive SHA256>'
```

The `--sha256` archive checksum is recommended; individual members are verified whether or not it is provided. The token is read from the process environment and is never embedded in URLs or committed to source. A Hugging Face or other hosting page URL is not necessarily a direct binary download link. Only publish a working link after testing it from a separate authorized account.

## Training data

The prepared dataset was not present among the compact source or case exports. Original manifests and dataset audit metadata are under `engine/evidence/` and `research/provenance/`; they do **not** recreate the missing training arrays. Training reproduction requires the prepared dataset bundle and original collection rights. Inference needs only the verified checkpoint and normalization metadata, not the complete training dataset.
