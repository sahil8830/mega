"""
FAISS Index Manager.

Manages three separate IndexFlatIP indices (visual, speech, OCR).
Indices are persisted to disk and a JSON metadata map is maintained
for reverse lookups from FAISS ID → MongoDB segment info.

IndexFlatIP uses inner product similarity. Since all embeddings are
L2-normalized, this is equivalent to cosine similarity.
"""
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

import faiss
import numpy as np

from app.config import get_settings

settings = get_settings()

INDEX_DIR = Path(settings.faiss_index_path)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

VISUAL_INDEX_PATH = str(INDEX_DIR / "faiss_visual.index")
SPEECH_INDEX_PATH = str(INDEX_DIR / "faiss_speech.index")
OCR_INDEX_PATH = str(INDEX_DIR / "faiss_ocr.index")
META_PATH = str(INDEX_DIR / "faiss_meta.json")

# Embedding dimension from CLIP ViT-B-32
EMBED_DIM = 512


@dataclass
class SegmentMeta:
    """Metadata stored alongside each FAISS vector for reverse lookup."""
    faiss_id: int
    video_id: str
    segment_id: str          # MongoDB _id of the Segment document
    chunk_id: int
    start_time: float
    end_time: float
    index_type: str          # "visual" | "speech" | "ocr"


class FaissManager:
    """
    Thread-safe FAISS index manager for visual, speech, and OCR indices.
    Singleton — use `get_faiss_manager()` to get the shared instance.
    """

    def __init__(self):
        self._lock = Lock()
        self._visual_index: faiss.IndexFlatIP = faiss.IndexFlatIP(EMBED_DIM)
        self._speech_index: faiss.IndexFlatIP = faiss.IndexFlatIP(EMBED_DIM)
        self._ocr_index: faiss.IndexFlatIP = faiss.IndexFlatIP(EMBED_DIM)

        # Maps faiss_id (int) → SegmentMeta dict — persisted as JSON
        self._meta: Dict[str, Dict] = {"visual": {}, "speech": {}, "ocr": {}}

        self._load()

    # ─── Public API ────────────────────────────────────────────────────────────

    def add_segment(
        self,
        visual_emb: np.ndarray,     # shape (512,)
        speech_emb: np.ndarray,     # shape (512,) — zero vector if no speech
        ocr_emb: np.ndarray,        # shape (512,) — zero vector if no OCR text
        video_id: str,
        segment_id: str,
        chunk_id: int,
        start_time: float,
        end_time: float,
    ) -> Dict[str, int]:
        """
        Add one segment's embeddings to all three indices.

        Returns:
            Dict with FAISS IDs: { "visual_id": int, "speech_id": int, "ocr_id": int }
        """
        with self._lock:
            v_id = self._visual_index.ntotal
            s_id = self._speech_index.ntotal
            o_id = self._ocr_index.ntotal

            self._visual_index.add(visual_emb.reshape(1, -1).astype(np.float32))
            self._speech_index.add(speech_emb.reshape(1, -1).astype(np.float32))
            self._ocr_index.add(ocr_emb.reshape(1, -1).astype(np.float32))

            base_meta = dict(
                video_id=video_id,
                segment_id=segment_id,
                chunk_id=chunk_id,
                start_time=start_time,
                end_time=end_time,
            )
            self._meta["visual"][str(v_id)] = {**base_meta, "faiss_id": v_id, "index_type": "visual"}
            self._meta["speech"][str(s_id)] = {**base_meta, "faiss_id": s_id, "index_type": "speech"}
            self._meta["ocr"][str(o_id)] = {**base_meta, "faiss_id": o_id, "index_type": "ocr"}

            return {"visual_id": v_id, "speech_id": s_id, "ocr_id": o_id}

    def search(
        self,
        query_emb: np.ndarray,     # shape (512,)
        index_type: str,           # "visual" | "speech" | "ocr"
        top_k: int = 10,
    ) -> List[Dict]:
        """
        Search one modality index.

        Returns:
            List of dicts: [{ score, video_id, segment_id, chunk_id, start_time, end_time }, ...]
        """
        index = self._get_index(index_type)
        meta_map = self._meta[index_type]

        if index.ntotal == 0:
            return []

        k = min(top_k, index.ntotal)
        query = query_emb.reshape(1, -1).astype(np.float32)
        scores, ids = index.search(query, k)

        results = []
        for score, fid in zip(scores[0], ids[0]):
            if fid == -1:
                continue
            meta = meta_map.get(str(fid), {})
            results.append({
                "score": float(score),
                "faiss_id": int(fid),
                **meta,
            })

        return results

    def save(self) -> None:
        """Persist all three indices and metadata to disk."""
        with self._lock:
            faiss.write_index(self._visual_index, VISUAL_INDEX_PATH)
            faiss.write_index(self._speech_index, SPEECH_INDEX_PATH)
            faiss.write_index(self._ocr_index, OCR_INDEX_PATH)
            with open(META_PATH, "w") as f:
                json.dump(self._meta, f)
        print(f"[FAISS] Saved indices — visual:{self._visual_index.ntotal} "
              f"speech:{self._speech_index.ntotal} ocr:{self._ocr_index.ntotal}")

    def stats(self) -> Dict:
        return {
            "visual_count": self._visual_index.ntotal,
            "speech_count": self._speech_index.ntotal,
            "ocr_count": self._ocr_index.ntotal,
        }

    # ─── Private Helpers ───────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load indices and metadata from disk if they exist."""
        loaded = []
        for path, attr, name in [
            (VISUAL_INDEX_PATH, "_visual_index", "visual"),
            (SPEECH_INDEX_PATH, "_speech_index", "speech"),
            (OCR_INDEX_PATH, "_ocr_index", "ocr"),
        ]:
            if os.path.exists(path):
                setattr(self, attr, faiss.read_index(path))
                loaded.append(name)

        if os.path.exists(META_PATH):
            with open(META_PATH) as f:
                self._meta = json.load(f)

        if loaded:
            print(f"[FAISS] Loaded existing indices: {loaded}")
        else:
            print("[FAISS] Starting with empty indices.")

    def _get_index(self, index_type: str) -> faiss.IndexFlatIP:
        mapping = {
            "visual": self._visual_index,
            "speech": self._speech_index,
            "ocr": self._ocr_index,
        }
        if index_type not in mapping:
            raise ValueError(f"Unknown index type: {index_type}. Must be visual|speech|ocr")
        return mapping[index_type]


# ─── Singleton ─────────────────────────────────────────────────────────────────
_faiss_manager: Optional[FaissManager] = None


def get_faiss_manager() -> FaissManager:
    """Return the shared FaissManager instance, creating it on first call."""
    global _faiss_manager
    if _faiss_manager is None:
        _faiss_manager = FaissManager()
    return _faiss_manager
