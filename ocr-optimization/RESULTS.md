# OCR acceleration experiment — 2026-10-12

Ten sampled frames from video 1791788736326-758448146, sequential runs:

| Runtime | Total OCR seconds | Text matching original |
| --- | ---: | ---: |
| Original PaddleOCR | 36.562 | Reference |
| Core ML text detector + original Paddle stages | 16.574 | 10/10 frames |

Observed speedup: 2.21x. Includes first inference; small sample, not a full-video guarantee. Background machine load was not controlled. Matching the original OCR does not establish ground-truth accuracy.

All five model weights, document orientation, UVDoc unwarping, text-line orientation, recognition, confidence threshold, image resolution and frame coverage remain unchanged. Only the detector execution runtime changes. Core ML accepted 270/276 detector graph nodes in five partitions; remaining nodes use ONNX CPU. This does not prove every supported node executes on GPU rather than Neural Engine/CPU.

Full-pipeline Core ML failed to compile UVDoc. Full-pipeline ONNX CPU ran but changed several recognized words in one dense sample. Neither configuration is selected.

At the time of this experiment, `ocr_acceleration.py` was prepared separately from the service. It attaches a replacement detector to initialized PaddleOCR. Initialization falls back from Core ML to ONNX CPU, then original Paddle. Inference failure latches back to original Paddle and retries the complete detector batch. Runtime errors are logged.

The experiment folder now lives at `mega/ocr-optimization/` inside the Git repository. The application's runtime implementation is [`../ml-service/app/services/ocr_acceleration.py`](../ml-service/app/services/ocr_acceleration.py), imported by `ocr_service.py`. Its configurable detector path is `OCR_DETECTOR_ONNX_DIR`. This folder contains the standalone experiment and recorded benchmark results.

Isolated dependencies: `/private/tmp/mega-onnx-deps`.
Converted models: `/private/tmp/mega-onnx-models`.
These are temporary experiment locations, not production installation paths.

For a new installation, install the ML-service dependencies and put the converted detector's `inference.onnx` and `inference.yml` in a persistent ignored model directory, then configure `OCR_DETECTOR_ONNX_DIR` and validate an indexing run. Temporary experiment paths above are specific to the original machine and are not included in Git.

Benchmark invocation (from ml-service):

```sh
.venv/bin/python ../ocr-optimization/benchmark.py paddle --extended --frames-dir "frames/YOUR_VIDEO_FRAME_DIRECTORY"
.venv/bin/python ../ocr-optimization/benchmark.py hybridcoreml --extended --frames-dir "frames/YOUR_VIDEO_FRAME_DIRECTORY" --onnx-models-dir "/path/to/converted-models"
```

Replace the placeholder paths with your sampled-frame directory and converted-model directory. The benchmark resolves repository paths from its own location and loads OCR configuration from the installed PaddleX package; it can be invoked from any working directory. `--paddle-models-dir` overrides the default PaddleX model cache. `--output` overrides the JSON output path, which otherwise defaults to `<mode>-benchmark.json` alongside this report.

Run benchmarks sequentially. Core ML requires access to Apple hardware outside the restricted tool sandbox. Original recorded JSON results are preserved alongside this report.
