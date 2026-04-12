"""Setup script: copy patched policy files to installed cogames package.

Runs as a subprocess before the policy is loaded. Copies patched files
from _patches/ to the installed cogames.policy directory, overwriting
the installed version with our fixes (no retry-sleep, HTTP pooling).
"""
import importlib
import os
import shutil
import sys

def main():
    # Find installed cogames.policy directory
    try:
        policy_mod = importlib.import_module("cogames.policy")
    except ImportError:
        print("ERROR: cogames.policy not found", file=sys.stderr)
        sys.exit(1)

    policy_dir = os.path.dirname(policy_mod.__file__)
    print(f"cogames.policy dir: {policy_dir}")

    patches_dir = os.path.join(os.getcwd(), "_patches")
    if not os.path.isdir(patches_dir):
        print(f"WARNING: _patches dir not found at {patches_dir}")
        return

    for filename in ["cross_role_policy.py", "llm_miner_policy.py"]:
        src = os.path.join(patches_dir, filename)
        dst = os.path.join(policy_dir, filename)
        if os.path.isfile(src):
            shutil.copy2(src, dst)
            print(f"Installed: {src} -> {dst}")
        else:
            print(f"WARNING: {src} not found")

    print("Setup complete")

if __name__ == "__main__":
    main()
