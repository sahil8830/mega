"""
Modality-Type Classifier.

Predicts which FAISS index (visual / speech / ocr) is most relevant
for a given query.  Implemented as a rule-based keyword classifier
(Phase 2 baseline) — will be upgraded to a trained MLP in Phase 3.

Returns:
  {
    "modality": "visual" | "speech" | "ocr" | "all",
    "weights": {"visual": float, "speech": float, "ocr": float},
    "confidence": "rule_based"
  }

The returned weights are used by the fusion layer to scale per-modality scores.
"""
import re
from typing import Dict

# ─── Keyword Banks ────────────────────────────────────────────────────────────

# Signals that the query is primarily about what was *said* (speech/audio)
_SPEECH_KEYWORDS = [
    r"\bexplains?\b", r"\bsay\b", r"\bsaid\b", r"\bdiscuss(?:es|ed|ing)?\b",
    r"\bmentions?\b", r"\btalk(?:s|ed|ing)?\b", r"\blecture(?:s|d|r)?\b",
    r"\bword\b", r"\bsentence\b", r"\bdescrib(?:es|ed|ing)?\b",
    r"\bnarrat\w+\b", r"\bpresent(?:s|ed|ing)?\b", r"\bspeak(?:s|ing)?\b",
    r"\bspoke\b", r"\bvoice\b", r"\baudio\b", r"\btranscript\b", r"\bquote\b",
    r"\bwhen.*says?\b", r"\bdefin(?:es|ed|ing|ition)?\b", r"\bsummariz\w+\b",
    r"\bstates?\b", r"\basserts?\b", r"\bargues?\b", r"\bteach(?:es|ing)?\b",
]

# Signals that the query is about text visible on screen (OCR)
_OCR_KEYWORDS = [
    r"\bcode\b", r"\bscript\b", r"\bprogram\b", r"\bfunction\b",
    r"\bslide\b", r"\btext\b", r"\bscreen\b", r"\bsubtitle\b",
    r"\bwrite\w*\b", r"\bdisplay\w*\b", r"\bshow\w*.*text\b",
    r"\bcaption\b", r"\btyp\w+\b", r"\blabel\b", r"\btitle\b",
    r"\bheading\b", r"\bformula\b", r"\bequation\b", r"\bmath\b",
]

# Signals that the query is about what is visually depicted
_VISUAL_KEYWORDS = [
    r"\bshow\b", r"\bappear\b", r"\bsee\b", r"\blook\b", r"\bcolor\b",
    r"\bscene\b", r"\bimage\b", r"\bvideo\b", r"\bframe\b", r"\bshot\b",
    r"\bvisual\b", r"\bpicture\b", r"\bphoto\b", r"\bbackground\b",
    r"\bperson\b", r"\bface\b", r"\bobject\b", r"\bcar\b", r"\bdraw\w*\b",
    r"\bdiagram\b", r"\bgraph\b", r"\bchart\b", r"\bwhiteboard\b",
]


def _count_matches(query_lower: str, patterns: list) -> int:
    return sum(1 for p in patterns if re.search(p, query_lower))


def classify_modality(query: str) -> Dict:
    """
    Classify a query into the most relevant modality and compute fusion weights.

    The weights are soft — dominant modality gets 0.6, others share 0.2 each.
    If no clear signal, returns equal weights (0.33 each).

    Args:
        query: Raw user query string.

    Returns:
        Dict with 'modality', 'weights', 'confidence'.
    """
    q = query.lower().strip()

    visual_score = _count_matches(q, _VISUAL_KEYWORDS)
    speech_score = _count_matches(q, _SPEECH_KEYWORDS)
    ocr_score = _count_matches(q, _OCR_KEYWORDS)

    total = visual_score + speech_score + ocr_score

    if total == 0:
        # No signal — equal weights
        return {
            "modality": "all",
            "weights": {"visual": 0.33, "speech": 0.33, "ocr": 0.34},
            "confidence": "rule_based",
        }

    # Determine dominant modality
    scores = {"visual": visual_score, "speech": speech_score, "ocr": ocr_score}
    dominant = max(scores, key=scores.get)
    max_score = scores[dominant]
    others = [k for k in scores if k != dominant]

    # Check if dominant is clearly leading (at least 2× others)
    second_max = max(scores[k] for k in others)
    if max_score >= 2 and max_score >= 2 * max(second_max, 1):
        # Strong dominant signal: 60% weight to dominant, 20% each to others
        weights = {k: 0.20 for k in scores}
        weights[dominant] = 0.60
    else:
        # Mixed signal: proportional weights based on scores
        norm = total
        weights = {k: round(v / norm, 4) for k, v in scores.items()}
        # Ensure they sum to 1
        diff = 1.0 - sum(weights.values())
        weights[dominant] += round(diff, 4)

    return {
        "modality": dominant if max_score >= 2 else "all",
        "weights": weights,
        "confidence": "rule_based",
        "debug_scores": scores,
    }
