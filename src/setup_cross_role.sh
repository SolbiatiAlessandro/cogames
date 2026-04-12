#!/bin/bash
# Setup script: copy bundled policy files to override installed cogames package.
# This ensures our fixes (no retry-sleep, HTTP pooling, scripted fallback) are used
# instead of the server's installed version which has the crash-causing retry loop.
set -e
POLICY_DIR=$(python -c "import cogames.policy; import os; print(os.path.dirname(cogames.policy.__file__))")
echo "cogames policy dir: $POLICY_DIR"
for f in cogames/policy/cross_role_policy.py cogames/policy/llm_miner_policy.py; do
    if [ -f "$f" ]; then
        cp "$f" "$POLICY_DIR/$(basename $f)"
        echo "Installed: $f -> $POLICY_DIR/$(basename $f)"
    else
        echo "WARNING: $f not found in bundle"
    fi
done
echo "Setup complete"
