# Exact OCR reuse and memory lifetime — 2026-10-14

The indexing pipeline now releases Whisper weights after transcription and before
frame processing. The next video reloads the same weights. This reduces retained
memory but adds model loading time per video; a full-video speedup has not been
measured. Disable with RELEASE_WHISPER_AFTER_TRANSCRIPTION=false.

OCR results are reused only for byte-identical input files within one indexing
run and the same engine/backend. The cache has a 16 MiB input/text payload limit,
is cleared on success or failure, and never caches inference failures. Python
object bookkeeping uses additional memory. OCR_EXACT_CACHE_MB=0 disables reuse.
Models, preprocessing, orientation, unwarping, frame sampling, confidence
filtering, chunk text ordering, and embedding code are retained.

Cumulative logs report actual inference calls, exact-cache hits, failures, and
separate document preprocessing, detection, orientation, and recognition times.
Individual frames taking at least five seconds also report their filename and
recognized region count. Timing wrappers exclude work done by their callers.

Validation:

- Regression tests cover exact reuse across filenames, changed bytes at the same
  filename, empty results, inference errors, error result objects, eviction,
  disabled caching, separate runs, detector fallback, timing transparency, and
  releasing transcription models without initializing unused runtimes.
- Existing chunk/embedding alignment, OCR confidence filtering, transcription
  backend, and indexing queue tests pass.
- Real Core ML + CPU run used two saved frames (chunk0010_frame0.jpg and
  chunk0132_frame0.jpg from 1791785315889-312208497), each followed by a copied
  duplicate. Chunk text matched the uncached baseline exactly. Four uncached
  calls took 5.684 seconds; two calls plus two cache hits took 2.794 seconds.
  Baseline ran first, so warm-up can influence timing. This is a small controlled
  duplicate-input demonstration, not a full-video speedup or accuracy guarantee.
- Recognition consumed about 1.9 of 2.8 seconds in the cached Core ML sample;
  detection and document preprocessing each consumed about 0.4 seconds.
- The two retained 816-frame sets had zero byte-identical cache hits in sequence.
  Exact caching therefore will not accelerate those sets. Broader optimization
  should use the new stage timings from representative long videos, retaining
  output-equivalence checks.

Run tests from ml-service:

```sh
.venv/bin/python -m unittest tests.test_ocr_runtime tests.test_indexing_batches tests.test_whisper_backends tests.test_indexing_queue
```
