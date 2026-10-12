import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import numpy as np
from PIL import Image
from app.services import indexing_pipeline as pipeline
from app.services import ocr_service as ocr
from app.services.segmentation import ChunkInfo


class BatchIndexingTests(unittest.IsolatedAsyncioTestCase):
    async def test_embeddings_stay_with_correct_chunks_and_bulk_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            paths = []
            for i in range(3):
                path = Path(folder) / f"{i}.jpg"
                Image.new("RGB", (8, 8), (i, i, i)).save(path)
                paths.append(str(path))
            chunks = [ChunkInfo(5, 20, 27, paths[:2]),
                      ChunkInfo(6, 24, 31, paths[2:]), ChunkInfo(7, 28, 35, [])]
            db = {"segments": SimpleNamespace(insert_many=AsyncMock(), bulk_write=AsyncMock())}
            faiss = Mock()
            faiss.add_segment.return_value = {"visual_id": 1, "speech_id": 2, "ocr_id": 3}

            def images(items):
                return np.array([[image.getpixel((0, 0))[0] + 1] * 512 for image in items], dtype=np.float32)

            def texts(items):
                return np.array([[len(text)] * 512 for text in items], dtype=np.float32)

            with patch.object(pipeline, "settings", SimpleNamespace(clip_batch_size=2)), \
                 patch.object(pipeline, "encode_images", side_effect=images) as image_calls, \
                 patch.object(pipeline, "encode_texts", side_effect=texts), \
                 patch.object(pipeline, "extract_text_from_chunk", side_effect=["score", "", "title"]):
                ids = await pipeline._process_batch(
                    chunks, {5: "speech", 7: "last"}, "6acc6f620d10522e066df687", db, faiss,
                    {"clip": 0, "ocr": 0, "database": 0},
                )
            docs = db["segments"].insert_many.call_args.args[0]
            self.assertEqual([doc["chunkId"] for doc in docs], [5, 6, 7])
            self.assertEqual([doc["transcript"] for doc in docs], ["speech", "", "last"])
            self.assertEqual([doc["ocrText"] for doc in docs], ["score", "", "title"])
            self.assertEqual(docs[0]["speechEmbedding"][0], len("A sports commentator says: speech"))
            self.assertEqual(docs[2]["ocrEmbedding"][0], len("On-screen text reads: title"))
            self.assertTrue(np.allclose(docs[0]["visualEmbedding"], np.ones(512) / np.sqrt(512)))
            self.assertEqual(docs[2]["visualEmbedding"], [0] * 512)
            self.assertEqual(docs[1]["speechEmbedding"], [0] * 512)
            self.assertEqual(len(ids), 3)
            self.assertEqual(image_calls.call_count, 2)
            db["segments"].insert_many.assert_awaited_once()
            db["segments"].bulk_write.assert_awaited_once()
            updates = db["segments"].bulk_write.call_args.args[0]
            for doc, update in zip(docs, updates):
                self.assertEqual(update._filter["_id"], doc["_id"])

    def test_all_ocr_frames_and_v3_results(self):
        result = [{"rec_texts": [" Goal ", "noise", "score"], "rec_scores": [0.99, 0.1, 0.8]}]
        self.assertEqual(ocr._parse_ocr_results(result), "Goal score")
        with patch.object(ocr, "get_ocr_engine", return_value=object()), \
             patch.object(ocr, "extract_text_from_frame", return_value="Goal") as extract:
            self.assertEqual(ocr.extract_text_from_chunk(["a", "b", "c", "d"]), "Goal")
            self.assertEqual(extract.call_count, 4)
            self.assertEqual([call.args[0] for call in extract.call_args_list], ["a", "b", "c", "d"])
