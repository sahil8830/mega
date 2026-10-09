"""
FAISS Index Manager - Per-user namespaced indices.

Each user gets their own set of three IndexFlatIP indices (visual, speech, OCR)
stored under faiss/{user_id}/. This provides complete isolation between users.

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

BASE_INDEX_DIR = Path(settings.faiss_index_path)
BASE_INDEX_DIR.mkdir(parents=True, exist_ok=True)

# Embedding dimension from CLIP ViT-B-32
EMBED_DIM = 512

# Global registry: user_id -> FaissManager instance
_user_managers: Dict[str, "FaissManager"] = {}
_registry_lock = Lock()


def _user_index_dir(user_id: str) -> Path:
    """Return (and create) the FAISS index directory for a specific user."""
    p = BASE_INDEX_DIR / user_id
    p.mkdir(parents=True, exist_ok=True)
    return p


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
    Thread-safe FAISS index manager for one user's visual, speech, and OCR indices.
    Use `get_faiss_manager(user_id)` to get the shared instance for a user.
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self._index_dir = _user_index_dir(user_id)
        self._lock = Lock()
        self._visual_index: faiss.IndexFlatIP = faiss.IndexFlatIP(EMBED_DIM)
        self._speech_index: faiss.IndexFlatIP = faiss.IndexFlatIP(EMBED_DIM)
        self._ocr_index: faiss.IndexFlatIP = faiss.IndexFlatIP(EMBED_DIM)

        # Maps faiss_id (int) -> SegmentMeta dict - persisted as JSON
        self._meta: Dict[str, Dict] = {"visual": {}, "speech": {}, "ocr": {}}

        self._load()

    @property
    def _visual_path(self) -> str:
        return str(self._index_dir / "faiss_visual.index")

    @property
    def _speech_path(self) -> str:
        return str(self._index_dir / "faiss_speech.index")

    @property
    def _ocr_path(self) -> str:
        return str(self._index_dir / "faiss_ocr.index")

    @property
    def _meta_path(self) -> str:
        return str(self._index_dir / "faiss_meta.json")

    # ─── Public API ────────────────────────────────────────────────────────────

    def add_segment(
        self,
        visual_emb: np.ndarray,     # shape (512,)
        speech_emb: np.ndarray,     # shape (512,) - zero vector if no speech
        ocr_emb: np.ndarray,        # shape (512,) - zero vector if no OCR text
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
            faiss.write_index(self._visual_index, self._visual_path)
            faiss.write_index(self._speech_index, self._speech_path)
            faiss.write_index(self._ocr_index, self._ocr_path)
            with open(self._meta_path, "w") as f:
                json.dump(self._meta, f)
        print(f"[FAISS:{self.user_id}] Saved - visual:{self._visual_index.ntotal} "
              f"speech:{self._speech_index.ntotal} ocr:{self._ocr_index.ntotal}")

    def stats(self) -> Dict:
        return {
            "user_id": self.user_id,
            "visual_count": self._visual_index.ntotal,
            "speech_count": self._speech_index.ntotal,
            "ocr_count": self._ocr_index.ntotal,
        }

    def reset_for_video(self, video_id: str) -> None:
        """
        Remove all FAISS entries for a specific video so it can be re-indexed.
        Rebuilds each index from the retained entries (all other videos).
        Saves to disk immediately.
        """
        with self._lock:
            for idx_type in ("visual", "speech", "ocr"):
                old_meta = self._meta.get(idx_type, {})
                old_index = self._get_index(idx_type)

                # Collect entries to KEEP (not belonging to this video)
                keep = [
                    (int(fid), m)
                    for fid, m in old_meta.items()
                    if m.get("video_id") != video_id
                ]

                # Rebuild index with only kept entries
                new_index = faiss.IndexFlatIP(EMBED_DIM)
                new_meta: Dict[str, Dict] = {}

                for new_fid, (old_fid, m) in enumerate(keep):
                    vec = np.zeros(EMBED_DIM, dtype=np.float32)
                    try:
                        old_index.reconstruct(old_fid, vec)
                    except Exception:
                        continue
                    new_index.add(vec.reshape(1, -1))
                    new_meta[str(new_fid)] = {**m, "faiss_id": new_fid}

                # Replace in-memory index + meta
                if idx_type == "visual":
                    self._visual_index = new_index
                elif idx_type == "speech":
                    self._speech_index = new_index
                else:
                    self._ocr_index = new_index
                self._meta[idx_type] = new_meta

            self.save()
            print(f"[FAISS:{self.user_id}] Cleared video {video_id} entries. "
                  f"Remaining: visual={self._visual_index.ntotal} "
                  f"speech={self._speech_index.ntotal} ocr={self._ocr_index.ntotal}")

    def full_reset(self) -> None:
        """Wipe all indices for this user. Use before a complete re-index."""
        with self._lock:
            self._visual_index = faiss.IndexFlatIP(EMBED_DIM)
            self._speech_index = faiss.IndexFlatIP(EMBED_DIM)
            self._ocr_index    = faiss.IndexFlatIP(EMBED_DIM)
            self._meta = {"visual": {}, "speech": {}, "ocr": {}}
            self.save()
            print(f"[FAISS:{self.user_id}] Full reset complete.")

    def get_video_embeddings(
        self,
        video_id: str,
        index: str = "visual",
    ) -> np.ndarray:
        """
        Retrieve all stored CLIP embeddings for a specific video.
        Used by Phase 5 temporal refinement for fine-grained localization.
        """
        meta_map = self._meta.get(index, {})
        faiss_index = self._get_index(index)

        if faiss_index.ntotal == 0:
            return np.empty((0, 512), dtype=np.float32)

        video_entries = [
            (int(fid), meta)
            for fid, meta in meta_map.items()
            if meta.get("video_id") == video_id
        ]

        if not video_entries:
            return np.empty((0, 512), dtype=np.float32)

        video_entries.sort(key=lambda x: x[1].get("chunk_id", x[0]))
        fids = np.array([e[0] for e in video_entries], dtype=np.int64)

        try:
            embs = np.zeros((len(fids), EMBED_DIM), dtype=np.float32)
            faiss_index.reconstruct_batch(fids, embs)
            return embs
        except Exception:
            embs = []
            for fid in fids:
                try:
                    v = np.zeros(EMBED_DIM, dtype=np.float32)
                    faiss_index.reconstruct(int(fid), v)
                    embs.append(v)
                except Exception:
                    pass
            return np.vstack(embs) if embs else np.empty((0, 512), dtype=np.float32)

    # ─── Private Helpers ───────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load indices and metadata from disk if they exist."""
        loaded = []
        for path, attr, name in [
            (self._visual_path, "_visual_index", "visual"),
            (self._speech_path, "_speech_index", "speech"),
            (self._ocr_path, "_ocr_index", "ocr"),
        ]:
            if os.path.exists(path):
                setattr(self, attr, faiss.read_index(path))
                loaded.append(name)

        if os.path.exists(self._meta_path):
            with open(self._meta_path) as f:
                self._meta = json.load(f)

        if loaded:
            print(f"[FAISS:{self.user_id}] Loaded existing indices: {loaded}")
        else:
            print(f"[FAISS:{self.user_id}] Starting with empty indices.")

    def _get_index(self, index_type: str) -> faiss.IndexFlatIP:
        mapping = {
            "visual": self._visual_index,
            "speech": self._speech_index,
            "ocr": self._ocr_index,
        }
        if index_type not in mapping:
            raise ValueError(f"Unknown index type: {index_type}. Must be visual|speech|ocr")
        return mapping[index_type]


# ─── Per-user Registry ─────────────────────────────────────────────────────────

def get_faiss_manager(user_id: str = "global") -> FaissManager:
    """
    Return the FaissManager for the given user_id, creating it on first call.
    Pass user_id='global' for backwards-compatible shared index.
    """
    global _user_managers
    with _registry_lock:
        if user_id not in _user_managers:
            _user_managers[user_id] = FaissManager(user_id)
        return _user_managers[user_id]
