# Publish SARScope and run it on Windows 11

This repository combines a saved-case research explorer with a local *real* Sentinel-1 inference workflow. **GitHub source and the static GitHub Pages site do not themselves run Python inference**. Inference runs locally on your authorized computer after importing the frozen model from `C:\SARPres\SARScope_selected_restore.zip`.

## A. Create a public GitHub repository and push the source

1. Install **Git for Windows**, **GitHub CLI**, and **64-bit Python 3.12**. If not installed, open a PowerShell terminal and run:

   ```powershell
   winget install --id Git.Git -e
   winget install --id GitHub.cli -e
   winget install --id Python.Python.3.12 -e
   ```

   Close and reopen the terminal so it sees new commands. Verify `git --version`, `gh --version`, and `py -3.12 --version`.

2. Extract the SARScope project ZIP to `C:\SARPres\SARScope\`, open that **folder** in VS Code, and open a PowerShell terminal (**Terminal > New Terminal**).

3. Authenticate to GitHub and run the included publisher:

   ```powershell
   gh auth login
   cd C:\SARPres\SARScope
   .\PUBLISH_PUBLIC.cmd
   ```

   The publisher checks that you are signed in as **keyurck7**, stages only allowed source files, checks for common secrets, commits the project, **creates the public repository `keyurck7/SARScope` if absent**, and pushes `main`. It will not overwrite an unrelated Git repository. On success it prints the public URL. If you prefer, open `https://github.com/new` and create an **empty** public repository named `SARScope` under `keyurck7` (do **not** initialize a README or .gitignore), then rerun the same publisher.

4. Visit the printed GitHub repository URL and verify the files appear. For the three-region static research explorer, open **Settings > Pages**, select **GitHub Actions** as the source and run the included `Publish static research demo` workflow from **Actions** if necessary. Verify the resulting Pages URL from the deployment report. This site displays stored evidence only, not new satellite queries.

## B. Run the full system in VS Code

**Existing publishing folder**: After step A, there is no need to clone again. Keep using `C:\SARPres\SARScope`. To get future changes, run `git pull --ff-only origin main` in that folder.

**Fresh clone** (e.g., another PC or a separate folder):

```powershell
cd C:\SARPres
git clone https://github.com/keyurck7/SARScope.git SARScope_Clone
cd .\SARScope_Clone
code .
```

Next, from the **repository root**:

1. Run `01_START.cmd`. It creates `.venv`, installs viewer libraries, and opens `http://127.0.0.1:8765`. Browse the four existing analyses. Stop this running server with **Ctrl+C** before the next step.
2. Verify your archive exists at `C:\SARPres\SARScope_selected_restore.zip` (Explorer may hide the `.zip` extension):

   ```powershell
   Test-Path 'C:\SARPres\SARScope_selected_restore.zip'
   ```

3. Run inference installation and import the **real frozen checkpoint**:

   ```powershell
   .\02_ENABLE_INFERENCE.cmd --bundle "C:\SARPres\SARScope_selected_restore.zip"
   ```

   This installs CPU PyTorch and inference dependencies, extracts only the validated checkpoint and two prepared metadata files, checks their SHA-256 digests, and runs the CPU model smoke test. The source archive and 22 rescue parts are not modified, copied into Git, or required to run locally.

4. Authenticate to your **authorized Google Earth Engine** project (replace the project ID if you use a different one):

   ```powershell
   .\03_SIGN_IN.cmd --project gae-application-308005
   ```

   This opens an interactive browser login and verifies Earth Engine initialization. Google Earth Engine credentials stay in your local account's credential store.

5. Verify the checkpoint and relaunch the app:

   ```powershell
   .\.venv\Scripts\python.exe scripts\model_assets.py status
   .\01_START.cmd
   ```

   In the status output, **`weights_verified` must be `true`**. Open `http://127.0.0.1:8765`, select a new latitude/longitude and 12-month period, and start analysis. New geographic queries require Earth Engine connectivity and usable Sentinel-1 observations.

## C. Troubleshooting and publishing rules

- **`gh`/`git`/`py` not found**: install using `winget` above and reopen VS Code/terminal.
- **Wrong GitHub account**: `gh auth switch` and confirm `gh api user --jq .login` outputs `keyurck7`.
- **Model import fails**: check archive path, completeness, `RESTORE_MANIFEST.json`, and checksum error; do not rename an unrelated checkpoint to `best.pt`.
- **Insufficient disk space**: the importer needs the size of only the three extracted inference assets plus safety margin, rather than uncompressing the entire rescue archive.
- **Model absent in status**: the public GitHub repository intentionally excludes the large frozen checkpoint and dataset. Keep them in `workspace/` (ignored by Git), or publish them separately only after verifying ownership, licensing and access policy.
- **Frontend changes**: install Node.js 22, then `cd frontend; npm ci; npm run build; cd ..` before running the local viewer. GitHub Actions also validates the frontend build.
- **New result sharing**: GitHub Pages serves the *saved* demo only. Running new authenticated Sentinel-1 jobs requires local `01_START.cmd` or a separately secured inference server.

For architecture and scientific qualifications see [`README.md`](README.md), [`docs/data-and-model.md`](docs/data-and-model.md), and [`docs/deployment.md`](docs/deployment.md).

## D. Choosing any historical 12-month period

The map explorer now provides separate **Start month** and **Start year** selectors. You may start in any month from **January 2015** through the latest start month allowing twelve fully completed calendar months. The selection immediately shows the first and last month of the 12-month range. The **Imagery window** dropdown offers a custom period or a shortcut to the latest completed twelve months.

After pulling a frontend source update, rebuild the local browser interface before restarting SARScope (Node.js 22 required):

```powershell
cd C:\SARPres\SARScope\frontend
npm ci
npm run build
cd ..\
.\01_START.cmd
```

This does not modify the frozen checkpoint or previously saved analyses. Years other than the previously evaluated 2021 reference remain scientifically unvalidated.
