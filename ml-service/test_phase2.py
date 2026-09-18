from app.services.query_expander import expand_query
from app.services.modality_classifier import classify_modality
from app.services.retrieval import retrieve
from app.routes.query_route import router as qr
from app.routes.search_route import router as sr
print("All Phase 2 modules imported OK")

# Smoke test modality classifier
tests = [
    "find where the professor explains gradient descent",
    "show the red car on the whiteboard",
    "find the code snippet for sorting algorithm",
    "what happens in the opening scene",
]
for q in tests:
    r = classify_modality(q)
    print(f"  [{r['modality']:8s}] {r['weights']}  '{q[:50]}'")
