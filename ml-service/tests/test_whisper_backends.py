import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.config import Settings
from app.services import whisper_asr as asr


class WhisperBackendTests(unittest.TestCase):
    def tearDown(self):
        asr._mlx_failed = False

    def test_release_clears_completed_models_without_loading_any(self):
        holder = SimpleNamespace(model=object(), model_path="same-weights")
        mx = SimpleNamespace(clear_cache=Mock())
        cuda = SimpleNamespace(is_initialized=lambda: False, empty_cache=Mock())
        loader = Mock()
        with patch.object(asr, "get_whisper_model", loader), \
             patch.dict(sys.modules, {
                 "mlx_whisper.transcribe": SimpleNamespace(ModelHolder=holder),
                 "mlx.core": mx, "torch": SimpleNamespace(cuda=cuda),
             }):
            asr.release_whisper_model()
        loader.assert_not_called()
        loader.cache_clear.assert_called_once()
        self.assertIsNone(holder.model)
        self.assertIsNone(holder.model_path)
        mx.clear_cache.assert_called_once()
        cuda.empty_cache.assert_not_called()

    def test_backend_selection(self):
        cases = [
            ("Darwin", "arm64", "mps", True, False, "mlx"),
            ("Darwin", "arm64", "mps", False, False, "pytorch"),
            ("Darwin", "x86_64", "mps", True, False, "pytorch"),
            ("Windows", "AMD64", "cuda", True, False, "pytorch"),
            ("Darwin", "arm64", "mps", True, True, "pytorch"),
        ]
        for system, machine, device, installed, force, expected in cases:
            with self.subTest(system=system, machine=machine, force=force):
                with patch("app.config.platform.system", return_value=system), \
                     patch("app.config.platform.machine", return_value=machine), \
                     patch("app.config.find_spec", return_value=object() if installed else None), \
                     patch.object(Settings, "device", property(lambda _: device)):
                    self.assertEqual(Settings(force_cpu=force).whisper_backend, expected)

    def test_mlx_preserves_translation_and_timestamps(self):
        for language, task in [("en", "transcribe"), ("hi", "translate")]:
            calls = []

            def transcribe(*args, **kwargs):
                calls.append(kwargs)
                return {"language": language, "segments": []}

            with patch.dict(sys.modules, {"mlx_whisper": SimpleNamespace(transcribe=transcribe)}):
                asr._transcribe_mlx("sample.mp4")
            self.assertEqual(calls[-1]["task"], task)
            self.assertEqual(calls[-1]["language"], language)
            self.assertTrue(calls[-1]["word_timestamps"])

    def test_mlx_failure_falls_back_for_rest_of_session(self):
        settings = SimpleNamespace(whisper_backend="mlx")
        result = {"segments": [
            {"start": 0, "end": 1, "text": " Hello",
             "words": [{"start": 0.1, "end": 0.8, "word": " Hello"}]},
            {"start": 1, "end": 2, "text": " segment fallback"},
        ]}
        with patch.object(asr, "settings", settings), \
             patch.object(asr, "_transcribe_mlx", side_effect=RuntimeError("GPU failed")) as mlx, \
             patch.object(asr, "_transcribe_pytorch", return_value=result) as cpu:
            expected = [{"start": 0.1, "end": 0.8, "text": "Hello"},
                        {"start": 1, "end": 2, "text": "segment fallback"}]
            self.assertEqual(asr.transcribe_video("sample.mp4"), expected)
            self.assertEqual(asr.transcribe_video("sample.mp4"), expected)
            mlx.assert_called_once()
            self.assertEqual(cpu.call_count, 2)
            self.assertEqual(asr.active_whisper_backend(), "pytorch")


if __name__ == "__main__":
    unittest.main()
