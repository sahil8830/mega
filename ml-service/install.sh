#!/usr/bin/env bash
# Activate your virtual environment first.
set -euo pipefail
cd "$(dirname "$0")"
python install.py "$@"
