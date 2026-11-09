# Deployment and shareable links

The system has **two deliberately different publishing targets**.

## 1. GitHub source + GitHub Pages read-only demo

Publish the whole **repository** to a new GitHub repository (suggested name `keyurck7/SARScope`). The `.github/workflows/ci.yml` builds the frontend and runs tests; `.github/workflows/pages.yml` deploys the self-contained `docs/index.html` static three-location explorer when GitHub Pages is enabled and the repo uses the `main` branch. In repository Settings → Pages, select **GitHub Actions** as source. This demo is public-readable if the repository is public and Pages is enabled, but cannot run a new satellite query.

```bash
cd SARScope
python scripts/repository_audit.py
python -m unittest discover -s tests -v
git init -b main
git add .
git status --short
git commit -m "Initialize SARScope research platform"
# Create an EMPTY new repository on GitHub first, then:
git remote add origin https://github.com/keyurck7/SARScope.git
git push -u origin main
```

Alternatively, on a machine with authenticated GitHub CLI: `gh repo create keyurck7/SARScope --public --source . --remote origin --push`. Do not use a separate existing project repository.

After publishing and enabling Pages, the expected **patterns** are `https://github.com/keyurck7/SARScope` for code and `https://keyurck7.github.io/SARScope/` for the static demo. These are **not live verified URLs** until the repository and Pages deployment actually exist.

## 2. Trusted dynamic inference service

The locally executable backend supports new coordinates, Earth Engine retrieval, and twelve monthly model predictions, **only once the genuine checkpoint and metadata are installed**, Earth Engine is authorized and the CPU smoke test has passed. Do not publish this write-enabled API unauthenticated to the internet. It has a loopback/trusted-user boundary, not a full user-account system.

For a public read-only demonstration of previously saved examples, build and run the Docker container:

```bash
docker compose up --build
# http://127.0.0.1:8765
```

To host this image on a server, configure HTTPS at the reverse proxy and deploy only in `SARSCOPE_PREVIEW=1` mode. No model or EE tokens are placed in the image. Deploying authenticated inference publicly needs additional authentication, job queueing, durable storage, quotas and operational monitoring before opening the network port.

## 3. Large artifact links

Store the weight restore archive and training dataset separately under a deliberately chosen private/public access policy (for example Hugging Face Hub or S3). Put actual tested URLs and their hashes into a release note; do not confuse local paths with shareable links. Keep raw credentials, training arrays requiring authorization, and other private files out of the GitHub repo.

## Publishing checklist

- CI passes and the page displays Cairo, Queens and Mauritania.
- `python scripts/model_assets.py status` reports the correct weight hash on the deployment machine.
- The trusted dynamic system completes a fresh new-coordinate inference and saves GeoTIFF + receipts.
- Review license and data redistribution permissions before publishing model weights or dataset.
- Test all live links in an unauthenticated browser (public) or a separate authorized account (private).
