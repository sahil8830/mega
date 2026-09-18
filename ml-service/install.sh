#!/usr/bin/env bash
# install.sh — Run this instead of `pip install -r requirements.txt` directly.
#
# WHY: openai-whisper==20240930 uses a legacy setup.py that imports pkg_resources,
# which is incompatible with setuptools >= 70 in isolated build environments.
# This script installs whisper with --no-build-isolation to work around this.

set -e

echo "📦 Upgrading pip, setuptools, wheel..."
python -m pip install --upgrade pip "setuptools==69.5.1" wheel

echo ""
echo "📦 Installing openai-whisper (requires --no-build-isolation)..."
pip install openai-whisper==20240930 --no-build-isolation

echo ""
echo "📦 Installing remaining requirements..."
pip install -r requirements.txt --ignore-installed openai-whisper

echo ""
echo "✅ All ML service dependencies installed successfully!"
