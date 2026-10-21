import unittest
from unittest.mock import patch
from types import SimpleNamespace

import numpy as np

from app.services import retrieval
from app.services.weighting_module import weighting_status
from app.services.clip_model import encode_texts


class RetrievalWeightTests(unittest.TestCase):
    def test_penalty_action_beats_commentary_with_real_model(self):
        # The action has strong frame evidence; the distractor mentions the
        # same topic in commentary. Exercise the real encoder and checkpoint.
        rows = {
            "visual": [("action", .8), ("commentary", .2)],
            "speech": [("action", .1), ("commentary", .9)],
            "ocr": [("action", .1), ("commentary", .1)],
        }
        def candidates(modality):
            return [dict(segment_id=sid, score=score) for sid, score in rows[modality]]
        manager = SimpleNamespace(score_segments=lambda q, ids, modality: candidates(modality))
        with patch.object(retrieval, "get_faiss_manager", return_value=manager), \
             patch.object(retrieval, "_multi_query_search_with",
                          side_effect=lambda mgr, emb, modality, k: candidates(modality)):
            for query in ("ronaldo going for panelty", "ronaldo going for penalty"):
                result = retrieval.retrieve(query, use_dynamic_weights=True)
                self.assertEqual(result["weighting_mode"], "dynamic")
                self.assertEqual(result["modality"], "visual")
                self.assertGreater(result["weights"]["visual"], .6)
                self.assertEqual(result["results"][0]["segment_id"], "action")

    def test_real_queries_change_weights_with_identical_scores_and_expansion(self):
        if not weighting_status()["checkpoint_exists"]:
            self.skipTest("Local trained checkpoint is unavailable")
        queries = ["a dog leaps over a fence",
                   "the narrator discusses the causes of inflation",
                   "read the equation written on the whiteboard"]
        embeddings = encode_texts(queries)
        weights = []
        for query, embedding in zip(queries, embeddings):
            # Every query gets identical candidates and the same GQE embedding.
            # Only the original user query changes, reproducing the missed case.
            def candidates(*args):
                return [dict(segment_id="best", score=0.3),
                        dict(segment_id="other", score=0.1)]

            manager = SimpleNamespace(score_segments=candidates)
            with patch.object(retrieval, "get_faiss_manager", return_value=manager), \
                 patch.object(retrieval, "_multi_query_search_with", side_effect=candidates), \
                 patch.object(retrieval, "encode_texts", return_value=embedding[None, :]) as encoder:
                result = retrieval.retrieve(query, embeddings[:1], use_dynamic_weights=True)
                encoder.assert_called_once_with([query])
                self.assertEqual(result["weighting_method"], "query_intent_and_mlp_v3")
                row = [result["weights"][key] for key in ("visual", "speech", "ocr")]
                self.assertAlmostEqual(sum(row), 1.0, places=6)
                weights.append(row)
        self.assertEqual([int(np.argmax(row)) for row in weights], [0, 1, 2])
        self.assertGreater(np.max(np.abs(np.array(weights[0]) - weights[1])), 0.1)
        self.assertGreater(np.max(np.abs(np.array(weights[1]) - weights[2])), 0.1)

    def search(self, scores, predictor=None):
        def candidates(manager, embeddings, modality, top_k):
            return [dict(segment_id=str(i), score=score)
                    for i, score in enumerate(scores[modality])]

        embeddings = np.zeros((2, 512), dtype=np.float32)
        embeddings[0, 0] = 1
        embeddings[1, 1] = 1
        manager = SimpleNamespace(score_segments=lambda q, sids, modality: candidates(None, None, modality, 20))
        with patch.object(retrieval, "get_faiss_manager", return_value=manager), \
             patch.object(retrieval, "encode_texts", return_value=embeddings[:1]), \
             patch.object(retrieval, "_multi_query_search_with", side_effect=candidates):
            if predictor is None:
                return retrieval.retrieve("test", embeddings, use_dynamic_weights=True)
            with patch("app.services.weighting_module.predict_fusion_weights",
                       side_effect=lambda q, s, **kwargs: predictor(q, s)):
                return retrieval.retrieve("test", embeddings, use_dynamic_weights=True)

    def test_raw_scores_and_normalized_embedding_reach_model(self):
        observed = []

        def predict(query, scores):
            observed.append((query, scores))
            return np.array([0.7, 0.2, 0.1])

        result = self.search({"visual": [0.8, 0.2], "speech": [0.4, 0.1],
                              "ocr": [0.3, 0.05]}, predict)
        np.testing.assert_allclose(observed[0][1], [0.8, 0.4, 0.3])
        self.assertAlmostEqual(float(np.linalg.norm(observed[0][0])), 1.0, places=6)
        self.assertEqual(result["weighting_mode"], "dynamic")
        self.assertAlmostEqual(result["results"][0]["fused_score"], 0.67)

    def test_missing_modality_preserves_relative_model_weights(self):
        result = self.search({"visual": [0.8, 0.2], "speech": [0.4, 0.1], "ocr": []},
                             lambda q, s: np.array([0.6, 0.3, 0.1]))
        self.assertAlmostEqual(result["weights"]["visual"], 2 / 3)
        self.assertAlmostEqual(result["weights"]["speech"], 1 / 3)
        self.assertEqual(result["weights"]["ocr"], 0)

    def test_zero_active_weight_uses_finite_available_weights(self):
        result = self.search({"visual": [0.8], "speech": [0.4], "ocr": []},
                             lambda q, s: np.array([0., 0., 1.]))
        self.assertEqual(result["weights"], {"visual": 0.5, "speech": 0.5, "ocr": 0.0})

    def test_model_failure_reports_fixed_fallback(self):
        def fail(q, s):
            raise FileNotFoundError("checkpoint missing")

        result = self.search({"visual": [0.8], "speech": [0.4], "ocr": [0.2]}, fail)
        self.assertEqual(result["weighting_mode"], "fixed")
        self.assertEqual(result["weights"], retrieval.DEFAULT_WEIGHTS)

    def test_local_checkpoint_changes_weights_with_retrieval_evidence(self):
        if not weighting_status()["checkpoint_exists"]:
            self.skipTest("Local trained checkpoint is unavailable")
        # Exercise the real checkpoint, with identical query and different raw
        # evidence, rather than asserting variation from a mocked predictor.
        visual = self.search({"visual": [0.85, 0.1], "speech": [0.1, 0.02],
                              "ocr": [0.05, 0.01]})
        speech = self.search({"visual": [0.1, 0.02], "speech": [0.85, 0.1],
                              "ocr": [0.05, 0.01]})
        self.assertEqual(visual["weighting_mode"], "dynamic")
        self.assertEqual(speech["weighting_mode"], "dynamic")
        self.assertGreater(visual["weights"]["visual"], speech["weights"]["visual"])
        self.assertGreater(speech["weights"]["speech"], visual["weights"]["speech"])


if __name__ == "__main__":
    unittest.main()
