"""Verify saved speech scores against the generator's missing-subtitle rule."""
import json
from pathlib import Path
import numpy as np
from generate_qvh_labels import _speech_signal

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'moment_detr'


def main():
    subs = {p.stem[3:].rsplit('_subs', 1)[0]
            for p in (SOURCE / 'features/clip_sub_features').glob('qid*.npz')}
    scan = json.loads((ROOT / 'runs/eda/full_source_scan.json').read_text())
    result = {}
    for split in ('train', 'val'):
        if not scan['splits'][split]['derived_alignment_verified']:
            raise ValueError(f'{split}: derived query alignment has not been verified')
        rows = [json.loads(x) for x in (SOURCE / f'data/highlight_{split}_release.jsonl').read_text().splitlines() if x.strip()]
        with np.load(ROOT / f'data/qvhighlights_{split}.npz', allow_pickle=False) as data:
            mask = np.array([r['vid'] not in subs for r in rows])
            expected = np.array([_speech_signal(r['query'])*0.5 for r in rows])[mask]
            actual = data['modality_scores'][mask, 1]
        result[split] = {'missing_subtitle_queries': int(mask.sum()),
                         'speech_fallback_match_count': int(np.isclose(actual, expected).sum()),
                         'zero_speech_fallback_count': int((actual == 0).sum()),
                         'note': 'Query embedding alignment verified by full_source_scan.json; rerun the full scan if inputs change.'}
    (ROOT / 'runs/eda/subtitle_fallback_audit.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
