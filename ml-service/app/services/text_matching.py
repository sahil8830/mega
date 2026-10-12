"""Literal topic evidence for transcript/OCR retrieval, alongside CLIP scores."""
import re


_QUERY_STOP_WORDS = set("""
a an the and or of to in on at for with from by about into as is are was were be
it its this that these those what which who how when where why do does did can
could would should me my you your please find search show video clip moment
person people someone speaker explaining explain explains explained talking
talk talks talked saying say says said speaking speaks read reading display
displayed screen tell tells describes describing description
""".split())


def query_terms(query: str) -> list[str]:
    words = re.findall(r"[^\W_]+", query.lower(), re.UNICODE)
    return list(dict.fromkeys(word for word in words
                              if word not in _QUERY_STOP_WORDS and len(word) > 1))


def term_pattern(term: str) -> str:
    # Prefix matching handles driver/drivers when the user types "drive".
    root = term[:-1] if len(term) > 4 and term.endswith("s") else term
    return r"\b" + re.escape(root) + (r"\w*" if len(root) >= 4 else r"s?\b")


def text_coverage(query: str, text: str) -> float:
    terms = query_terms(query)
    if not terms or not text:
        return 0.0
    return sum(bool(re.search(term_pattern(term), text, re.IGNORECASE))
               for term in terms) / len(terms)


async def find_text_candidates(db, query: str, video_ids: list) -> list[dict]:
    """Fetch only topic-matching text from videos in the caller's scope."""
    terms = query_terms(query)
    if not terms or not video_ids:
        return []
    pattern = "|".join(term_pattern(term) for term in terms)
    return await db["segments"].find(
        {"videoId": {"$in": video_ids}, "$or": [
            {"transcript": {"$regex": pattern, "$options": "i"}},
            {"ocrText": {"$regex": pattern, "$options": "i"}},
        ]},
        {"_id": 1, "transcript": 1, "ocrText": 1},
    ).to_list(None)
