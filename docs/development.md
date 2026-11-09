# Local development in VS Code

## Quick opening

Extract `SARScope_GitHub_Ready.zip` and open the **SARScope** folder in VS Code (File → Open Folder). The workspace includes code-completion recommendations, test tasks and Python debug configurations. After creating the environment, use **Python: Select Interpreter** in VS Code to choose `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on macOS/Linux. **Do not open a ZIP as a project**.

## Windows, saved cases first

- Install **64-bit Python 3.12**, then run `01_START.cmd` at the repository root. It creates `.venv`, installs pinned viewer requirements and starts `http://127.0.0.1:8765`.
- To activate new data acquisition, run `02_ENABLE_INFERENCE.cmd --bundle "C:\path\to\SARScope_selected_restore.zip"`, then `03_SIGN_IN.cmd --project YOUR_EE_PROJECT`.
- Current frontend source quality panel requires a rebuilt frontend: from `frontend/`, `npm ci` then `npm run build`. Use Node 22 for this workflow.

## macOS / Linux, saved cases first

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-viewer.txt
python serve.py --open
```

The backend reads the built UI from `frontend/dist`. To edit TypeScript, run `cd frontend && npm ci && npm run build` and refresh. Run `python -m unittest discover -s tests -v` for existing API and reliability tests.

**Note:** the original Windows bootstrap is the primary tested installation path. Its CPU PyTorch wheel installation and model import are not yet demonstrated on macOS/Linux in this build environment.

## Environment and credentials

The `.env.example` is an example only. The code does not automatically load dotenv; configure `SARSCOPE_WORKSPACE` and `SARSCOPE_PREVIEW` in your terminal/VS Code if overriding defaults. Keep Earth Engine credentials only in your local authorized Google Earth Engine credential location.

## Operations

- `GET /api/status` reports whether model, Python dependencies, Earth Engine auth and local CPU smoke test are present.
- `GET /api/cases` and `GET /api/cases/{id}` read saved cases without the checkpoint.
- `POST /api/analyze` launches a worker only after the runtime checks pass, on a locally trusted app.
- `GET /api/jobs/{id}` reads status.
- `docs/index.html` is a fully static three-case research demonstration requiring no backend.
