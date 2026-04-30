#!/usr/bin/env python3
"""Upload policy to tournament server, bypassing CLI compat check."""
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx

from cogames.cli.client import TournamentServerClient
from cogames.cli.login import DEFAULT_COGAMES_SERVER
from cogames.cli.submit import DEFAULT_SUBMIT_SERVER
from mettagrid.policy.submission import POLICY_SPEC_FILENAME, SubmissionPolicySpec


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "lessandro-ohm-mani-padme-hum"
    season = sys.argv[2] if len(sys.argv) > 2 else "beta-cvc"

    spec = SubmissionPolicySpec(
        class_path="cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy",
        data_path=None,
        init_kwargs={"scripted_miners": True, "scripted_aligners": True},
        setup_script=None,
    )

    src_dir = Path("src/cogames/policy")
    init_files = [
        Path("src/cogames/__init__.py"),
        Path("src/cogames/policy/__init__.py"),
    ]

    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        zip_path = Path(tmp.name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        zipf.writestr(POLICY_SPEC_FILENAME, spec.model_dump_json())
        for init_file in init_files:
            if init_file.exists():
                zipf.write(init_file, arcname=str(init_file))
        for py_file in src_dir.glob("*.py"):
            zipf.write(py_file, arcname=str(py_file))

    print(f"Bundle: {zip_path} ({zip_path.stat().st_size / 1024:.0f} KB)")

    from cogames.cli.login import CoGamesAuthenticator
    authenticator = CoGamesAuthenticator()
    token = authenticator.load_token(DEFAULT_COGAMES_SERVER)
    if not token:
        print("ERROR: Not authenticated. Run: cogames login")
        sys.exit(1)

    headers = {"Authorization": f"Bearer {token}"}

    print("Getting presigned URL...")
    resp = httpx.post(f"{DEFAULT_SUBMIT_SERVER}/stats/policies/submit/presigned-url", headers=headers, timeout=60.0)
    resp.raise_for_status()
    presigned = resp.json()
    upload_url = presigned["upload_url"]
    upload_id = presigned["upload_id"]

    print("Uploading to S3...")
    with open(zip_path, "rb") as f:
        resp = httpx.put(upload_url, content=f, headers={"Content-Type": "application/zip"}, timeout=600.0)
    resp.raise_for_status()

    print(f"Completing upload (name={name}, season={season})...")
    resp = httpx.post(
        f"{DEFAULT_SUBMIT_SERVER}/stats/policies/submit/complete",
        headers=headers,
        json={"upload_id": upload_id, "name": name, "season": season},
        timeout=120.0,
    )
    resp.raise_for_status()
    result = resp.json()

    print(f"\nUpload successful!")
    print(f"  Name: {result.get('name')}:v{result.get('version')}")
    print(f"  ID: {result.get('id')}")
    print(f"  Pools: {result.get('pools')}")
    zip_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
