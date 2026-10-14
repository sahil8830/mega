"""Per-indexing-run exact-input reuse and transparent OCR stage timings."""
from collections import OrderedDict, defaultdict
from contextvars import ContextVar
from time import perf_counter


_active_run = ContextVar("ocr_run", default=None)


def active_ocr_run():
    return _active_run.get()


class OCRRun:
    """Bounded, run-local cache. Bytes are compared exactly, not perceptually."""

    def __init__(self, max_bytes=16 * 1024 * 1024):
        self.max_bytes = max_bytes
        self.cache = OrderedDict()
        self.cache_bytes = 0
        self.hits = 0
        self.inferences = 0
        self.failures = 0
        self.stage_seconds = defaultdict(float)

    def __enter__(self):
        self._token = _active_run.set(self)
        return self

    def __exit__(self, *exc):
        _active_run.reset(self._token)
        self.cache.clear()
        self.cache_bytes = 0

    def key(self, image_path, engine):
        if self.max_bytes <= 0:
            return None
        try:
            # Do not allocate a large image merely to discover it cannot fit.
            with open(image_path, "rb") as stream:
                data = stream.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                return None
        except OSError:
            return None
        return (*self.engine_token(engine), data)

    @staticmethod
    def engine_token(engine):
        # A detector fallback changes execution backend: don't mix cached output.
        pipeline = getattr(getattr(engine, "paddlex_pipeline", None), "_pipeline", None)
        detector = getattr(pipeline, "text_det_model", None)
        return (id(engine), bool(getattr(detector, "failed", False)))

    def lookup(self, key):
        if key is not None and key in self.cache:
            self.cache.move_to_end(key)
            self.hits += 1
            return self.cache[key]
        return None

    def remember(self, key, text):
        if key is None:
            return
        size = len(key[2]) + len(text.encode("utf-8"))
        if size > self.max_bytes:
            return
        while self.cache and self.cache_bytes + size > self.max_bytes:
            old_key, old_text = self.cache.popitem(last=False)
            self.cache_bytes -= len(old_key[2]) + len(old_text.encode("utf-8"))
        self.cache[key] = text
        self.cache_bytes += size

    def summary(self):
        stages = ", ".join(f"{name} {seconds:.1f}s" for name, seconds in self.stage_seconds.items())
        return (f"OCR cumulative: {self.inferences} inferred, {self.hits} exact-cache hits, "
                f"{self.failures} failures; {stages or 'no stage timings yet'}")


class TimedPredictor:
    """Time generator execution only, excluding work performed by its caller."""

    def __init__(self, original, name):
        self.original = original
        self.name = name

    def __getattr__(self, name):
        return getattr(self.original, name)

    def __call__(self, *args, **kwargs):
        run = active_ocr_run()
        if run is None:
            yield from self.original(*args, **kwargs)
            return
        started = perf_counter()
        try:
            iterator = iter(self.original(*args, **kwargs))
        finally:
            run.stage_seconds[self.name] += perf_counter() - started
        while True:
            started = perf_counter()
            try:
                result = next(iterator)
            except StopIteration:
                return
            finally:
                run.stage_seconds[self.name] += perf_counter() - started
            yield result


def instrument_ocr(ocr):
    pipeline = getattr(getattr(ocr, "paddlex_pipeline", None), "_pipeline", None)
    for attr, name in (
        ("doc_preprocessor_pipeline", "document"),
        ("text_det_model", "detection"),
        ("textline_orientation_model", "orientation"),
        ("text_rec_model", "recognition"),
    ):
        original = getattr(pipeline, attr, None)
        if original is not None and not isinstance(original, TimedPredictor):
            setattr(pipeline, attr, TimedPredictor(original, name))
