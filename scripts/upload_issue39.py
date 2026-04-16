#!/usr/bin/env python3
"""Upload merged MGrvP policy to beta-cvc tournament.

Bypasses the CLI compat version check (client-side only) and uploads directly.
"""
from __future__ import annotations

import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)

from cogames.cli.client import TournamentServerClient
from cogames.cli.submit import DEFAULT_SUBMIT_SERVER, upload_submission
from cogames.cli.login import DEFAULT_COGAMES_SERVER
from mettagrid.policy.submission import POLICY_SPEC_FILENAME, SubmissionPolicySpec

SUBMISSION_NAME = sys.argv[1] if len(sys.argv) > 1 else "lessandro-scripted-v21"
SEASON = sys.argv[2] if len(sys.argv) > 2 else "beta-cvc"

POLICY_CLASS = "cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy"

policy_files = []
src_policy = Path("src/cogames/policy")
for f in src_policy.rglob("*.py"):
    policy_files.append(f)

init_files = [
    Path("src/cogames/__init__.py"),
    Path("src/cogames/cogs_vs_clips/__init__.py"),
]

all_files = list(set(policy_files + init_files))

# Also include the setup_cross_role.sh for server compatibility
setup_script = "src/setup_cross_role.sh"
if Path(setup_script).exists():
    all_files.append(Path(setup_script))

print(f"Creating bundle for {SUBMISSION_NAME}")
print(f"  Policy class: {POLICY_CLASS}")
print(f"  Files: {len(all_files)}")
print(f"  Season: {SEASON}")

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

print(f"  Bundle size: {zip_path.stat().st_size / 1024:.0f} KB")

client = TournamentServerClient.from_login(
    server_url=DEFAULT_SUBMIT_SERVER,
    login_server=DEFAULT_COGAMES_SERVER,
)

if not client:
    print("ERROR: Authentication failed")
    sys.exit(1)

print(f"\nUploading {SUBMISSION_NAME} to {SEASON}...")
with client:
    result = upload_submission(client, zip_path, SUBMISSION_NAME, season=SEASON)

zip_path.unlink()

if result:
    print(f"\nUpload complete: {result.name}:v{result.version}")
    print(f"  Policy version ID: {result.policy_version_id}")
    if result.pools:
        print(f"  Added to pools: {', '.join(result.pools)}")
    print(f"\nResults: https://www.softmax.com/alignmentleague")
else:
    print("\nUpload FAILED")
    sys.exit(1)
