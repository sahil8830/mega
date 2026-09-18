@echo off
REM install.bat — Run this on Windows instead of `pip install -r requirements.txt` directly.
REM
REM Why not plain `pip install -r requirements.txt`?
REM  1. openai-whisper needs --no-build-isolation (pkg_resources issue with setuptools 70+)
REM  2. torch + torchvision must be installed from PyTorch's official index (https://download.pytorch.org/whl/cpu)
REM     The PyPI wheels are missing C++ extensions (torchvision::nms etc.)

echo [1/4] Upgrading pip and setuptools...
python -m pip install --upgrade pip "setuptools==69.5.1" wheel

echo.
echo [2/4] Installing torch + torchvision from PyTorch official CPU index...
pip install torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu

echo.
echo [3/4] Installing openai-whisper (requires --no-build-isolation)...
pip install openai-whisper==20240930 --no-build-isolation

echo.
echo [4/4] Installing remaining requirements...
pip install -r requirements.txt --ignore-installed torch torchvision openai-whisper

echo.
echo All ML service dependencies installed successfully!
echo Run: uvicorn main:app --reload --port 8001
