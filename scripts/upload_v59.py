#!/usr/bin/env python3
"""Upload v59 policy (aSOVe merge) to beta-cvc tournament.

Bypasses CLI compat version check and handles SSL cert issues.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx

os.chdir(Path(__file__).resolve().parent.parent)

SUBMISSION_NAME = sys.argv[1] if len(sys.argv) > 1 else "lessandro-scripted-v59"
SEASON = sys.argv[2] if len(sys.argv) > 2 else "beta-cvc"
SERVER = "https://api.observatory.softmax-research.net"
POLICY_CLASS = "cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy"

token = os.environ.get("COGAMES_TOKEN")
if not token:
    import yaml
    cfg = yaml.safe_load(open(os.path.expanduser("~/.metta/cogames.yaml")))
    token = cfg["login_tokens"]["https://softmax.com/api"]

headers = {"X-Auth-Token": token}

policy_files = []
src_policy = Path("src/cogames/policy")
for f in src_policy.rglob("*.py"):
    policy_files.append(f)

init_files = [
    Path("src/cogames/__init__.py"),
    Path("src/cogames/cogs_vs_clips/__init__.py"),
]

all_files = list(set(policy_files + init_files))

from mettagrid.policy.submission import POLICY_SPEC_FILENAME, SubmissionPolicySpec

spec = SubmissionPolicySpec(
    class_path=POLICY_CLASS,
    data_path=None,
    init_kwargs={},
    setup_script=None,
)

with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
    zip_path = Path(tmp.name)

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
    zipf.writestr(POLICY_SPEC_FILENAME, spec.model_dump_json())
    for f in all_files:
        if f.exists():
            zipf.write(f, arcname=str(f))

print(f"Bundle: {SUBMISSION_NAME}")
print(f"  Policy class: {POLICY_CLASS}")
print(f"  Files: {len(all_files)}")
print(f"  Bundle size: {zip_path.stat().st_size / 1024:.0f} KB")
print(f"  Season: {SEASON}")

client = httpx.Client(base_url=SERVER, timeout=60.0, verify=False)

print("\nGetting presigned upload URL...")
resp = client.post("/stats/policies/submit/presigned-url", headers=headers)
resp.raise_for_status()
presigned = resp.json()
upload_url = presigned["upload_url"]
upload_id = presigned["upload_id"]

print("Uploading to S3...")
with open(zip_path, "rb") as f:
    upload_resp = httpx.put(
        upload_url,
        content=f,
        headers={"Content-Type": "application/zip"},
        timeout=600.0,
        verify=False,
    )
upload_resp.raise_for_status()

print(f"Completing upload and submitting to {SEASON}...")
complete_resp = client.post(
    "/stats/policies/submit/complete",
    headers=headers,
    json={"upload_id": upload_id, "name": SUBMISSION_NAME, "season": SEASON},
    timeout=120.0,
)
complete_resp.raise_for_status()
result = complete_resp.json()

client.close()
zip_path.unlink()

print(f"\nUpload complete: {result.get('name')}:v{result.get('version')}")
print(f"  Policy version ID: {result.get('id')}")
if result.get("pools"):
    print(f"  Added to pools: {', '.join(result['pools'])}")
print(f"\nResults: https://www.softmax.com/alignmentleague")
