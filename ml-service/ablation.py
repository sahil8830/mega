"""
Ablation Experiment — Fixed-Weight vs Dynamic-Weight Fusion (Phase 3, Step 3.4).

Evaluates both approaches on a test set of (query, ground-truth segment) pairs.

Metrics:
  - R@1  (Recall at 1):  Is the ground-truth in top-1 result?
  - R@5  (Recall at 5):  Is the ground-truth in top-5 results?
  - mIoU (mean IoU):     Temporal overlap between predicted and ground-truth windows
  - MRR  (Mean Reciprocal Rank): 1/rank of first correct hit

Ground-truth:
  Loaded from MongoDB 'segments' collection.
  If no real test set is available, generates synthetic queries using CLIP embeddings
  of existing segments as query proxies (leave-one-out style).

Usage:
  cd ml-service
  venv\\Scripts\\activate
  python ablation.py --top-k 5
  python ablation.py --top-k 5 --test-file data/test_pairs.json
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))


# ─── Metrics ──────────────────────────────────────────────────────────────────

def compute_iou(pred_start: float, pred_end: float, gt_start: float, gt_end: float) -> float:
    """Temporal IoU between two intervals."""
    intersection = max(0.0, min(pred_end, gt_end) - max(pred_start, gt_start))
    union = max(1e-8, max(pred_end, gt_end) - min(pred_start, gt_start))
    return intersection / union


def recall_at_k(results: List[Dict], gt_segment_id: str, k: int) -> float:
    """1.0 if gt_segment_id appears in top-k results, else 0.0."""
    top_k = [r["segment_id"] for r in results[:k]]
    return 1.0 if gt_segment_id in top_k else 0.0


def mean_reciprocal_rank(results: List[Dict], gt_segment_id: str) -> float:
    """1/rank of first hit, or 0 if not found."""
    for i, r in enumerate(results):
        if r["segment_id"] == gt_segment_id:
            return 1.0 / (i + 1)
    return 0.0


def best_iou(results: List[Dict], gt_start: float, gt_end: float, top_k: int) -> float:
    """Max IoU across top-k results."""
    ious = [
        compute_iou(r["start_time"], r["end_time"], gt_start, gt_end)
        for r in results[:top_k]
    ]
    return max(ious) if ious else 0.0


# ─── Test Set ─────────────────────────────────────────────────────────────────

async def load_test_pairs_from_mongo(mongodb_uri: str, max_pairs: int = 200) -> List[Dict]:
    """
    Generate synthetic test pairs from MongoDB segments.
    For each segment: use its CLIP visual embedding as a fake query embedding,
    and the segment itself as the ground truth.
    This is a leave-one-out proxy test (real queries would come from QVHighlights).
    """
    from motor.motor_asyncio import AsyncIOMotorClient
    import numpy as np

    client = AsyncIOMotorClient(mongodb_uri)
    db_name = mongodb_uri.rsplit("/", 1)[-1].split("?")[0] or "mega"
    db = client[db_name]

    docs = await db["segments"].find(
        {},
        {
            "_id": 1,
            "videoId": 1,
            "startTime": 1,
            "endTime": 1,
            "transcript": 1,
            "ocrText": 1,
            "visualEmbedding": 1,
        }
    ).limit(max_pairs).to_list(None)
    client.close()

    pairs = []
    for doc in docs:
        emb = np.array(doc.get("visualEmbedding", [0.0]*512), dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 1e-8:
            emb = emb / norm
        pairs.append({
            "query": doc.get("transcript") or doc.get("ocrText") or "visual query",
            "query_embedding": emb.tolist(),
            "gt_segment_id": str(doc["_id"]),
            "gt_start": doc.get("startTime", 0.0),
            "gt_end": doc.get("endTime", 10.0),
            "video_id": str(doc.get("videoId", "")),
        })

    print(f"[Ablation] Loaded {len(pairs)} test pairs from MongoDB.")
    return pairs


def load_test_pairs_from_file(path: str) -> List[Dict]:
    """Load test pairs from a JSON file."""
    with open(path) as f:
        return json.load(f)


# ─── Evaluation ───────────────────────────────────────────────────────────────

def evaluate_one_mode(
    test_pairs: List[Dict],
    use_dynamic_weights: bool,
    top_k: int,
    mode_name: str,
) -> Dict:
    """Run retrieval on all test pairs and aggregate metrics."""
    from app.services.retrieval import retrieve
    import numpy as np

    r1_scores, r5_scores, iou_scores, mrr_scores = [], [], [], []

    for i, pair in enumerate(test_pairs):
        query = pair["query"]
        gt_sid = pair["gt_segment_id"]
        gt_start = pair.get("gt_start", 0.0)
        gt_end = pair.get("gt_end", 10.0)

        q_emb = pair.get("query_embedding")
        rep_embs = np.array([q_emb], dtype=np.float32) if q_emb else None

        result = retrieve(
            query=query,
            representative_embeddings=rep_embs,
            top_k=top_k,
            use_dynamic_weights=use_dynamic_weights,
        )
        results = result["results"]

        r1 = recall_at_k(results, gt_sid, 1)
        r5 = recall_at_k(results, gt_sid, min(5, top_k))
        iou = best_iou(results, gt_start, gt_end, top_k)
        mrr = mean_reciprocal_rank(results, gt_sid)

        r1_scores.append(r1)
        r5_scores.append(r5)
        iou_scores.append(iou)
        mrr_scores.append(mrr)

        if (i + 1) % 20 == 0:
            print(f"  [{mode_name}] {i+1}/{len(test_pairs)} done...")

    return {
        "mode": mode_name,
        "n_queries": len(test_pairs),
        "R@1":  round(float(np.mean(r1_scores)),  4),
        "R@5":  round(float(np.mean(r5_scores)),  4),
        "mIoU": round(float(np.mean(iou_scores)), 4),
        "MRR":  round(float(np.mean(mrr_scores)), 4),
    }


def print_ablation_table(fixed: Dict, dynamic: Dict):
    """Print a formatted ablation comparison table."""
    print("\n" + "="*60)
    print("ABLATION: Fixed-Weight vs Dynamic-Weight Fusion")
    print("="*60)
    print(f"{'Metric':<10} {'Fixed':>10} {'Dynamic':>10} {'Delta':>10}")
    print("-"*60)
    for metric in ["R@1", "R@5", "mIoU", "MRR"]:
        f_val = fixed[metric]
        d_val = dynamic[metric]
        delta = d_val - f_val
        sign = "+" if delta >= 0 else ""
        print(f"{metric:<10} {f_val:>10.4f} {d_val:>10.4f} {sign}{delta:>9.4f}")
    print("="*60)
    print(f"N queries: {fixed['n_queries']}")
    print()


# ─── Entry Point ──────────────────────────────────────────────────────────────

def main(args):
    # Load test pairs
    if args.test_file and Path(args.test_file).exists():
        test_pairs = load_test_pairs_from_file(args.test_file)
        print(f"[Ablation] Loaded {len(test_pairs)} pairs from {args.test_file}")
    else:
        print("[Ablation] No test file provided — loading from MongoDB...")
        test_pairs = asyncio.run(
            load_test_pairs_from_mongo(args.mongodb_uri, max_pairs=args.max_pairs)
        )

    if not test_pairs:
        print("[Ablation] No test pairs available. Index some videos first.")
        print("  Tip: Upload a video via POST /api/videos/upload then run this again.")
        return

    print(f"\n[Ablation] Evaluating {len(test_pairs)} queries with top_k={args.top_k}...\n")

    # Evaluate both modes
    print("[Ablation] Running FIXED-WEIGHT baseline...")
    fixed_results = evaluate_one_mode(test_pairs, False, args.top_k, "Fixed")

    print("[Ablation] Running DYNAMIC-WEIGHT MLP...")
    dynamic_results = evaluate_one_mode(test_pairs, True, args.top_k, "Dynamic")

    print_ablation_table(fixed_results, dynamic_results)

    # Save results
    output = {"fixed": fixed_results, "dynamic": dynamic_results}
    out_path = Path(__file__).parent / "ablation_results.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"[Ablation] Results saved to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fixed vs Dynamic Weight Ablation")
    parser.add_argument("--top-k",      type=int, default=5)
    parser.add_argument("--test-file",  type=str, default=None)
    parser.add_argument("--mongodb-uri",type=str, default="mongodb://localhost:27017/mega")
    parser.add_argument("--max-pairs",  type=int, default=200,
                        help="Max test pairs to load from MongoDB if no test file")
    args = parser.parse_args()
    main(args)
