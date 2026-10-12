"""Install dependencies using NVIDIA CUDA where detected, otherwise CPU."""
import argparse
import platform
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def select_backend(requested="auto"):
    if requested != "auto":
        if requested == "cuda" and platform.system() == "Darwin":
            raise ValueError("CUDA is unavailable on macOS; use auto or cpu.")
        return requested
    if platform.system() not in ("Linux", "Windows"):
        return "cpu"
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            result = subprocess.run(
                [smi, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return "cuda"
        except (OSError, subprocess.TimeoutExpired):
            pass
    return "cpu"


def pip(*args):
    subprocess.run([sys.executable, "-m", "pip", *args], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args()
    if not (3, 10) <= sys.version_info[:2] <= (3, 12):
        parser.error("Use Python 3.10–3.12 (Python 3.11 recommended for these pins).")
    backend = select_backend(args.device)
    print(f"Installing PyTorch for {backend.upper()}", flush=True)
    pip("install", "--upgrade", "pip", "setuptools==69.5.1", "wheel")
    torch_args = ["install", "--upgrade", "torch==2.3.1", "torchvision==0.18.1"]
    # macOS wheels are distributed on PyPI; Windows/Linux use official indexes.
    if platform.system() != "Darwin":
        torch_args += ["--index-url", "https://download.pytorch.org/whl/" +
                       ("cu121" if backend == "cuda" else "cpu")]
    pip(*torch_args)
    pip("install", "openai-whisper==20240930", "--no-build-isolation")
    requirements = Path(__file__).with_name("requirements.txt")
    # Already installed separately; avoid Whisper's isolated build and keep the
    # selected PyTorch build. No --ignore-installed (which reinstalls packages).
    lines = [line for line in requirements.read_text().splitlines()
             if not line.startswith(("torch==", "torchvision==", "openai-whisper=="))]
    with tempfile.TemporaryDirectory() as directory:
        remaining = Path(directory) / "requirements.txt"
        remaining.write_text("\n".join(lines) + "\n")
        pip("install", "-r", str(remaining))
    subprocess.run([sys.executable, "-c",
                    "import torch; print('Runtime device:', "
                    "'cuda' if torch.cuda.is_available() else "
                    "'mps' if torch.backends.mps.is_available() else 'cpu')"], check=True)
    print("Installed. Start with: uvicorn main:app --reload --port 8001")


if __name__ == "__main__":
    main()
