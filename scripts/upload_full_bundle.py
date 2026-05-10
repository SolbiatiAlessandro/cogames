"""Upload a full policy bundle to the Softmax tournament server.

Creates a zip containing ALL .py files from src/cogames/policy/ (and the parent
__init__.py), so the server-side import chain resolves correctly without shadowing
the installed cogames package with a partial bundle.
"""

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx
import yaml


def load_token():
    t = os.environ.get("COGAMES_TOKEN")
    if t:
        return t
    cfg = yaml.safe_load(open(os.path.expanduser("~/.metta/cogames.yaml")))
    return cfg["login_tokens"]["https://softmax.com/api"]


def create_bundle_zip(output_path: Path, class_path: str, init_kwargs: dict | None = None) -> None:
    src_root = Path(__file__).resolve().parent.parent / "src"
    cogames_dir = src_root / "cogames"
    policy_dir = cogames_dir / "policy"

    policy_spec = {
        "class_path": class_path,
        "data_path": None,
        "init_kwargs": init_kwargs or {},
        "setup_script": None,
    }

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("policy_spec.json", json.dumps(policy_spec))

        # cogames/__init__.py (the parent package)
        init_file = cogames_dir / "__init__.py"
        if init_file.exists():
            zf.write(init_file, arcname="cogames/__init__.py")

        # All .py files from cogames/policy/
        for py_file in sorted(policy_dir.glob("*.py")):
            arcname = f"cogames/policy/{py_file.name}"
            zf.write(py_file, arcname=arcname)

    print(f"Bundle created: {output_path} ({output_path.stat().st_size / 1024:.1f} KB)")

    # List contents
    with zipfile.ZipFile(output_path, "r") as zf:
        print(f"Contents ({len(zf.namelist())} files):")
        for name in sorted(zf.namelist()):
            info = zf.getinfo(name)
            print(f"  {name} ({info.file_size} bytes)")


def upload(zip_path: Path, name: str, season: str | None = None):
    token = load_token()
    server = "https://api.observatory.softmax-research.net"
    headers = {"X-Auth-Token": token}

    # Step 1: Get presigned upload URL
    print("\nGetting presigned upload URL...")
    resp = httpx.post(f"{server}/stats/policies/submit/presigned-url",
                      headers=headers, timeout=60.0)
    resp.raise_for_status()
    data = resp.json()
    upload_url = data["upload_url"]
    upload_id = data["upload_id"]
    print(f"Upload ID: {upload_id}")

    # Step 2: Upload to S3
    print("Uploading to S3...")
    with open(zip_path, "rb") as f:
        resp = httpx.put(upload_url, content=f,
                         headers={"Content-Type": "application/zip"},
                         timeout=600.0)
    resp.raise_for_status()
    print("Upload complete")

    # Step 3: Complete the upload
    print(f"Completing upload as '{name}'...")
    payload = {"upload_id": upload_id, "name": name}
    if season:
        payload["season"] = season
    resp = httpx.post(f"{server}/stats/policies/submit/complete",
                      headers=headers, json=payload, timeout=120.0)
    resp.raise_for_status()
    result = resp.json()
    print(f"Policy uploaded: {result['name']}:v{result['version']} (id={result['id']})")
    if result.get("pools"):
        print(f"Submitted to pools: {result['pools']}")
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Upload full policy bundle")
    parser.add_argument("--name", required=True, help="Policy name")
    parser.add_argument("--season", default=None, help="Season to submit to")
    parser.add_argument("--class-path", default="cogames.policy.machina_llm_roles_policy.MachinaLLMRolesPolicy")
    parser.add_argument("--dry-run", action="store_true", help="Create bundle but don't upload")
    parser.add_argument("--kw", nargs="*", default=[], help="Init kwargs as key=value pairs")
    args = parser.parse_args()

    init_kwargs = {}
    for kv in args.kw:
        k, v = kv.split("=", 1)
        init_kwargs[k] = v

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / "bundle.zip"
        create_bundle_zip(zip_path, args.class_path, init_kwargs=init_kwargs or None)

        if args.dry_run:
            print("\nDry run — bundle created but not uploaded")
            return

        result = upload(zip_path, args.name, args.season)
        return result


if __name__ == "__main__":
    main()
