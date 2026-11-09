#!/usr/bin/env python3
"""Conservative pre-publication check on files staged for a GitHub repository.

This does not certify licensing or the absence of every possible secret. It catches
common credential formats, private key blocks and accidentally staged archives.
"""
from __future__ import annotations
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                       check=True, capture_output=True).stdout.split(b"\0")
paths = [Path(item.decode("utf-8")) for item in files if item]
problems: list[str] = []
patterns = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "GitHub credential": re.compile(rb"\b(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_)[A-Za-z0-9_]{20,}"),
    "Google API credential": re.compile(rb"\bAIza[0-9A-Za-z_-]{25,}"),
    "AWS key ID": re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "Hugging Face token": re.compile(rb"\bhf_[A-Za-z0-9]{28,}"),
}
text_extensions = {".md", ".py", ".ts", ".tsx", ".js", ".css", ".html",
                   ".json", ".yaml", ".yml", ".txt", ".csv", ".cmd", ".ps1",
                   ".toml", ".ini", ".ipynb", ".gitignore", ".gitattributes"}
allowed_zips = {"case_export.zip"}
scanned = 0
for path in paths:
    full = ROOT / path
    if not full.is_file():
        problems.append(f"Missing staged file: {path}")
        continue
    if path.suffix.lower() == ".zip":
        if path.name not in allowed_zips or "sample/cases/" not in path.as_posix():
            problems.append(f"Archive should not be published in Git: {path}")
            continue
        with zipfile.ZipFile(full) as archive:
            for info in archive.infolist():
                if info.filename.lower().endswith((".key", ".pem", ".pt", ".pth", ".ckpt")):
                    problems.append(f"Sensitive payload in example archive: {path}")
                if Path(info.filename).suffix.lower() in text_extensions and info.file_size < 8_000_000:
                    data = archive.read(info)
                    for name, pattern in patterns.items():
                        if pattern.search(data):
                            problems.append(f"{name} pattern in archive: {path}::{info.filename}")
            scanned += 1
    elif path.suffix.lower() in text_extensions or path.name in {"Dockerfile", "Makefile"}:
        if full.stat().st_size > 12_000_000:
            problems.append(f"Unexpectedly large text file: {path}")
            continue
        data = full.read_bytes()
        for name, pattern in patterns.items():
            if pattern.search(data):
                problems.append(f"{name} pattern found in: {path}")
        scanned += 1
    if any(part in {"workspace", "secrets", ".venv", "node_modules"} for part in path.parts):
        problems.append(f"Runtime/secret directory tracked: {path}")

if problems:
    print("PUBLIC RELEASE CHECK FAILED:", file=sys.stderr)
    for problem in problems:
        print(" - " + problem, file=sys.stderr)
    raise SystemExit(1)
print(f"PASS: Checked {len(paths)} staged paths ({scanned} content checks); no known secret patterns detected.")
print("NOTE: Review source, sample data and research-report distribution rights before public release.")
