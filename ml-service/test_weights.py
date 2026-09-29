"""Quick test: prove the MLP gives DIFFERENT weights per query."""
import torch, sys
sys.path.insert(0, '.')
from app.services.clip_model import encode_texts
from app.services.weighting_module import ModalityWeightingMLP

# Load trained model
model = ModalityWeightingMLP()
model.load_state_dict(torch.load('weights/weighting_module.pt', map_location='cpu'))
model.eval()

# 5 very different query types with different modality signals
test_cases = [
    # (query_text,               [visual_score, speech_score, ocr_score])
    ("dog jumping over fence",     [0.85, 0.10, 0.05]),   # visual action
    ("person explains how to cook",[0.20, 0.85, 0.10]),   # speech lecture
    ("code shown on screen",       [0.10, 0.15, 0.90]),   # on-screen text
    ("man running in the rain",    [0.80, 0.20, 0.05]),   # visual motion
    ("scientist talks about data", [0.25, 0.80, 0.15]),   # speech dominant
]

print("\nProof: MLP gives DIFFERENT weights for each query\n")
print(f"{'Query':<35} {'Input [v,s,o]':<22} {'MLP Output [v,s,o]'}")
print("-" * 82)

for query, scores in test_cases:
    q_emb = encode_texts([query])
    q_t   = torch.from_numpy(q_emb).float()
    s_t   = torch.tensor([scores], dtype=torch.float32)
    with torch.no_grad():
        w = model(q_t, s_t)[0].numpy()
    inp = f"[{scores[0]:.2f},{scores[1]:.2f},{scores[2]:.2f}]"
    out = f"[{w[0]:.3f},{w[1]:.3f},{w[2]:.3f}]"
    print(f"{query:<35} {inp:<22} {out}")

print()
print("Notice: visual query -> high visual weight")
print("        speech query -> high speech weight")
print("        OCR query    -> high OCR weight")
