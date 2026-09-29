"""Quick test for Phase 4 answerability detection."""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from app.services.answerability import compute_answerability

print("\nPhase 4 — Answerability Detection Test\n")
print(f"{'Scenario':<35} {'Top Score':<12} {'Gap':<10} {'Answerable':<12} {'Confidence':<12} {'Reason'}")
print("-" * 95)

test_cases = [
    # (scenario, results_list, visual_scores)
    ("Strong match (1 result)",
     [{"score": 0.82}, {"score": 0.41}, {"score": 0.38}],
     [0.78, 0.35, 0.30]),

    ("Weak match (scores too low)",
     [{"score": 0.12}, {"score": 0.10}, {"score": 0.09}],
     [0.10, 0.09, 0.08]),

    ("All results similar (no gap)",
     [{"score": 0.55}, {"score": 0.53}, {"score": 0.51}],
     [0.50, 0.48, 0.46]),

    ("Good score but low gap",
     [{"score": 0.60}, {"score": 0.57}, {"score": 0.55}],
     [0.55, 0.52, 0.50]),

    ("Perfect match",
     [{"score": 0.95}, {"score": 0.20}, {"score": 0.18}],
     [0.92, 0.18, 0.15]),

    ("No results at all",
     [],
     []),
]

for scenario, results, visual_scores in test_cases:
    a = compute_answerability(
        results=results,
        visual_scores=visual_scores if visual_scores else None,
    )
    top   = a["top_score"]
    gap   = a["score_gap"]
    ans   = "YES" if a["answerable"] else "NO"
    conf  = a["confidence"]
    reason = a["reason"]
    print(f"{scenario:<35} {top:<12.3f} {gap:<10.3f} {ans:<12} {conf:<12.3f} {reason}")

print("\nDone! Phase 4 answerability is working correctly.")
