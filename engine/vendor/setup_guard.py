#!/usr/bin/env python3
"""One-command isolated setup plus data preparation and two GPU smoke runs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import venv
import zipfile


STACK_PROBE = """
import json
from importlib.metadata import version
import torch, torchvision, numpy
print(json.dumps({
 'cuda': torch.cuda.is_available(),
 'versions': {n: version(n) for n in ('torch','torchvision','numpy')},
 'runtime': {'torch':torch.__version__, 'torchvision':torchvision.__version__},
 'paths': {'torch':torch.__file__, 'torchvision':torchvision.__file__, 'numpy':numpy.__file__}
}))
"""


def constraints_text(stack):
    # pip matches distribution metadata, which may omit the runtime CUDA suffix.
    return "".join(f"{name}=={stack['versions'][name]}\n" for name in ("torch", "torchvision", "numpy"))


def check_install_plan(plan):
    for item in plan.get("install", []):
        name = item["metadata"]["name"].lower().replace("_", "-")
        if name in {"torch", "torchvision", "numpy", "triton"} or name.startswith("nvidia-"):
            raise RuntimeError(f"Refusing installer plan that changes the existing compute stack: {name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    args = ap.parse_args()
    project, work = args.project.expanduser().resolve(), args.work.expanduser().resolve()
    if not (project / "data/chips").is_dir():
        raise SystemExit("Expected existing PROJECT/data/chips directory")
    if work == project or project in work.parents or work in project.parents:
        raise SystemExit("Use a separate sibling work directory outside the existing project")
    work.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parent
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"

    def call(command):
        print("Running:", " ".join(map(str, command)), flush=True)
        with (work / "run.log").open("a") as log:
            p = subprocess.Popen(list(map(str, command)), cwd=root, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in p.stdout:
                print(line, end="", flush=True)
                log.write(line); log.flush()
            if p.wait():
                raise RuntimeError(f"Command failed with exit code {p.returncode}")

    try:
        import torch
        import torchvision
        import numpy
        if not torch.cuda.is_available():
            raise RuntimeError(f"{sys.executable} cannot access CUDA. Use the server's CUDA PyTorch interpreter.")
        if torch.__version__.split("+")[0] != "2.9.0" or torchvision.__version__.split("+")[0] != "0.24.0":
            raise RuntimeError("Expected reviewed PyTorch 2.9.0 / torchvision 0.24.0; environment changed. Return diagnostics before replacing GPU packages.")
        constraints = work / "base_constraints.txt"
        target = work / ".venv"
        if not (target / "bin/python").exists():
            venv.EnvBuilder(with_pip=True, system_site_packages=True).create(target)
        python = target / "bin/python"
        before = json.loads(subprocess.check_output([str(python), "-c", STACK_PROBE], text=True, env=env))
        if not before["cuda"]:
            raise RuntimeError("The isolated environment did not inherit CUDA PyTorch")
        print("Inherited compute stack:", json.dumps(before), flush=True)
        (work / "compute_stack_before.json").write_text(json.dumps(before, indent=2))
        constraints.write_text(constraints_text(before))
        # Inherit the working CUDA stack; install additions ONLY in this venv.
        install = [python, "-m", "pip", "install", "--disable-pip-version-check", "-c", constraints, "-r", root / "requirements.txt"]
        plan_file = work / "install_plan.json"
        call(install + ["--dry-run", "--report", plan_file])
        check_install_plan(json.loads(plan_file.read_text()))
        call(install)
        after = json.loads(subprocess.check_output([str(python), "-c", STACK_PROBE], text=True, env=env))
        (work / "compute_stack_after.json").write_text(json.dumps(after, indent=2))
        if after != before:
            raise RuntimeError("Compute stack changed during setup; training stopped. Return setup_review.zip.")
        freeze = subprocess.check_output([str(python), "-m", "pip", "freeze"], text=True, env=env)
        (work / "requirements.lock.txt").write_text(freeze)
        call([python, root / "run.py", "stage1", "--project", project, "--work", work])
        print(f"\nDone. Return {work / 'baseline_review.zip'}", flush=True)
    except Exception:
        (work / "setup_failure.txt").write_text(traceback.format_exc())
        dest = work / "setup_review.zip"
        with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
            for name in ("setup_failure.txt", "run.log", "environment.json", "failure.txt", "compute_stack_before.json", "compute_stack_after.json"):
                p = work / name
                if p.exists():
                    z.write(p, name)
        print(f"Setup stopped. Return {dest}", flush=True)
        raise


if __name__ == "__main__":
    main()
