import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.services import ocr_service as ocr
from app.services.ocr_runtime import OCRRun, TimedPredictor, active_ocr_run


class OCRReuseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = []
        for name, data in [('a.jpg', b'frame A'), ('b.jpg', b'frame A'), ('c.jpg', b'frame B')]:
            path = Path(self.temp.name) / name
            path.write_bytes(data)
            self.paths.append(str(path))
        self.engine = SimpleNamespace(predict=Mock(side_effect=self.predict))

    def predict(self, path):
        text = 'A' if Path(path).read_bytes() == b'frame A' else 'B'
        return [{'rec_texts': [text, 'rejected'], 'rec_scores': [0.99, 0.5]}]

    def test_exact_reuse_preserves_chunk_text_and_order(self):
        chunks = [self.paths, list(reversed(self.paths))]
        with patch.object(ocr, 'get_ocr_engine', return_value=self.engine):
            baseline = [ocr.extract_text_from_chunk(paths) for paths in chunks]
            self.engine.predict.reset_mock()
            with OCRRun() as run:
                cached = [ocr.extract_text_from_chunk(paths) for paths in chunks]
                self.assertEqual(cached, baseline)
                self.assertEqual(cached, ['A B', 'B A'])
                self.assertEqual(run.hits, 4)
                self.assertEqual(self.engine.predict.call_count, 2)
            self.assertEqual(run.cache_bytes, 0)
            self.assertIsNone(active_ocr_run())

    def test_changed_file_is_not_reused(self):
        with patch.object(ocr, 'get_ocr_engine', return_value=self.engine), OCRRun():
            self.assertEqual(ocr.extract_text_from_frame(self.paths[0]), 'A')
            Path(self.paths[0]).write_bytes(b'frame B')
            self.assertEqual(ocr.extract_text_from_frame(self.paths[0]), 'B')
            self.assertEqual(self.engine.predict.call_count, 2)

    def test_failure_is_retried_and_successful_empty_text_is_cached(self):
        self.engine.predict.side_effect = [RuntimeError('temporary'), [{'rec_texts': [], 'rec_scores': []}]]
        with patch.object(ocr, 'get_ocr_engine', return_value=self.engine), OCRRun() as run:
            for _ in range(3):
                self.assertEqual(ocr.extract_text_from_frame(self.paths[0]), '')
            self.assertEqual(self.engine.predict.call_count, 2)
            self.assertEqual(run.failures, 1)
            self.assertEqual(run.hits, 1)

    def test_run_isolation_and_disabled_cache(self):
        with patch.object(ocr, 'get_ocr_engine', return_value=self.engine):
            for _ in range(2):
                with OCRRun():
                    ocr.extract_text_from_frame(self.paths[0])
            with OCRRun(0):
                ocr.extract_text_from_frame(self.paths[0])
                ocr.extract_text_from_frame(self.paths[0])
        self.assertEqual(self.engine.predict.call_count, 4)

    def test_pipeline_error_result_is_not_cached(self):
        self.engine.predict.side_effect = [[{'error': 'temporary'}], self.predict(self.paths[0])]
        with patch.object(ocr, 'get_ocr_engine', return_value=self.engine), OCRRun():
            self.assertEqual(ocr.extract_text_from_frame(self.paths[0]), '')
            self.assertEqual(ocr.extract_text_from_frame(self.paths[0]), 'A')
            self.assertEqual(self.engine.predict.call_count, 2)

    def test_eviction_and_oversized_input(self):
        with patch.object(ocr, 'get_ocr_engine', return_value=self.engine), OCRRun(8) as run:
            for path in [self.paths[0], self.paths[2], self.paths[0]]:
                ocr.extract_text_from_frame(path)
                self.assertLessEqual(run.cache_bytes, 8)
            self.assertEqual(self.engine.predict.call_count, 3)
            Path(self.paths[0]).write_bytes(b'x' * 9)
            self.assertIsNone(run.key(self.paths[0], self.engine))

    def test_backend_fallback_does_not_reuse_previous_results(self):
        detector = SimpleNamespace(failed=False)
        self.engine.paddlex_pipeline = SimpleNamespace(_pipeline=SimpleNamespace(text_det_model=detector))
        with patch.object(ocr, 'get_ocr_engine', return_value=self.engine), OCRRun():
            ocr.extract_text_from_frame(self.paths[0])
            detector.failed = True
            ocr.extract_text_from_frame(self.paths[0])
            self.assertEqual(self.engine.predict.call_count, 2)

    def test_timer_preserves_values_exceptions_and_excludes_consumer_time(self):
        clock = [0]
        def generate():
            clock[0] += 2
            yield 'first'
            clock[0] += 3
            raise ValueError('original error')
        with patch('app.services.ocr_runtime.perf_counter', side_effect=lambda: clock[0]), OCRRun() as run:
            wrapped = iter(TimedPredictor(generate, 'stage')())
            self.assertEqual(next(wrapped), 'first')
            clock[0] += 100
            with self.assertRaisesRegex(ValueError, 'original error'):
                next(wrapped)
            self.assertEqual(run.stage_seconds['stage'], 5)


if __name__ == '__main__':
    unittest.main()
