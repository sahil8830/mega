import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import numpy as np

from app.services import retrieval
from app.services.faiss_manager import FaissManager
from app.services.localizer import refine_segment
from app.services.modality_classifier import classify_modality
from app.services.query_expander import _valid_variants, _cluster_and_select
from app.services.text_matching import text_coverage
from app.routes.search_route import SearchRequest, search_endpoint, _expand_window


class RelevanceTests(unittest.TestCase):
    def test_explaining_is_speech_even_with_person_subject(self):
        for query in ("person explaining about iOS", "person explaining what is llm"):
            weights = classify_modality(query)["weights"]
            self.assertGreater(weights["speech"], weights["visual"])

    def test_expansion_rejects_observed_generated_garbage(self):
        query = "person explaining what is llm"
        variants = ["if __name__ == '__main__': a = [] for i in range(4): print(a)",
                    "what is llm " * 20,
                    "from sys import stdin, stdout",
                    "a narrator explains an LLM"]
        self.assertEqual(_valid_variants(query, variants), [variants[-1]])

    def test_clustering_always_keeps_original_query(self):
        vectors = np.eye(4, 512, dtype=np.float32)
        with patch("app.services.query_expander.encode_texts", return_value=vectors):
            result = _cluster_and_select("what is llm", ["explain llm", "describe llm", "define llm"])
        self.assertEqual(result["representatives"][0], "what is llm")
        np.testing.assert_array_equal(result["representative_embeddings"][0], vectors[0])

    def test_text_matching_ignores_query_instructions_and_handles_driver(self):
        self.assertEqual(text_coverage("person explaining about iOS", "iOS is Apple's operating system"), 1)
        self.assertEqual(text_coverage("person explaining about iOS", "a person explaining Android"), 0)
        self.assertEqual(text_coverage("person talking about device drive", "APIs called device drivers"), 1)

    def test_fine_speech_match_keeps_its_indexed_timestamps(self):
        segment = dict(start_time=64, end_time=71, video_id="video",
                       modality_weights={"visual": .1, "speech": .8, "ocr": .1})
        manager = Mock()
        result = refine_segment(np.ones(512), segment, manager)
        self.assertEqual((result["start_time"], result["end_time"]), (64, 71))
        self.assertFalse(result["refined"])
        manager.get_video_timeline.assert_not_called()

    def test_visual_refinement_uses_real_times_not_two_second_positions(self):
        query = np.array([1., 0.])
        starts = np.array([100., 104., 108., 112., 116., 120., 124.])
        manager = SimpleNamespace(get_video_timeline=lambda *a, **kw:
                                  (np.tile(query, (len(starts), 1)), starts, starts + 7))
        result = refine_segment(query, dict(video_id="v", start_time=100, end_time=131), manager)
        self.assertTrue(result["refined"])
        self.assertGreaterEqual(result["start_time"], 100)
        self.assertLessEqual(result["end_time"], 131)

    def test_context_window_never_exceeds_video_duration(self):
        self.assertEqual(_expand_window(280, 287, 285.4), (270.4, 285.4))
        self.assertEqual(_expand_window(0, 5, 5), (0, 5))

    def test_rescoring_uses_all_modalities_and_excludes_deleted_videos(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch("app.services.faiss_manager.BASE_INDEX_DIR", Path(folder)):
            manager = FaissManager("test")
            query = np.zeros(512, np.float32)
            query[0] = 1
            def vector(score):
                v = np.zeros(512, np.float32)
                v[:2] = [score, np.sqrt(1 - score * score)]
                return v
            manager.add_segment(vector(.9), vector(.6), vector(.5), "owned", "good", 0, 64, 71)
            manager.add_segment(vector(1), vector(1), vector(1), "deleted", "stale", 0, 0, 7)
            # Expansion points at the unrelated axis. Final scores must use query.
            with patch.object(retrieval, "get_faiss_manager", return_value=manager), \
                 patch.object(retrieval, "encode_texts", return_value=query[None, :]):
                result = retrieval.retrieve("topic", vector(-1)[None, :],
                    modality_weights={"visual": .5, "speech": .3, "ocr": .2},
                    allowed_video_ids={"owned"})
            self.assertEqual(len(result["results"]), 1)
            hit = result["results"][0]
            self.assertEqual(hit["segment_id"], "good")
            self.assertAlmostEqual(hit["speech_score"], .6)
            self.assertAlmostEqual(hit["fused_score"], .73)
            vectors, starts, ends = manager.get_video_timeline("owned")
            self.assertEqual(starts.tolist(), [64])
            self.assertEqual(ends.tolist(), [71])


class SearchEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_translated_original_query_is_used_for_scoring(self):
        db = {name: Mock() for name in ("videos", "segments")}
        db["videos"].find.return_value.to_list = AsyncMock(return_value=[])
        db["segments"].find.return_value.to_list = AsyncMock(return_value=[])
        result = dict(query="what is llm", results=[], modality="all", weights={},
                      total_candidates=0, weighting_mode="fixed")
        with patch("app.db.get_db", return_value=db), \
             patch.object(retrieval, "retrieve", return_value=result) as search:
            response = await search_endpoint(SearchRequest(query="LLM क्या है", translated_query="what is llm"))
        self.assertEqual(search.call_args.kwargs["query"], "what is llm")
        self.assertEqual(response.query, "LLM क्या है")

    async def test_min_confidence_actually_removes_results(self):
        db = {name: Mock() for name in ("videos", "segments")}
        db["videos"].find.return_value.to_list = AsyncMock(return_value=[{"_id": "v", "duration": 100}])
        db["segments"].find.return_value.to_list = AsyncMock(return_value=[])
        result = dict(query="test", results=[dict(fused_score=.7)],
                      modality="all", weights={}, total_candidates=1, weighting_mode="fixed")
        with patch("app.db.get_db", return_value=db), \
             patch.object(retrieval, "retrieve", return_value=result), \
             patch("app.services.answerability.compute_answerability", return_value={
                 "answerable": True, "confidence": .7, "reason": "high_confidence"}):
            response = await search_endpoint(SearchRequest(query="test", min_confidence=.9))
        self.assertFalse(response.answerable)
        self.assertEqual(response.results, [])
        self.assertEqual(response.answerability_reason, "below_min_confidence")


if __name__ == "__main__":
    unittest.main()
