"""Read every source NPZ; summarize integrity, distributions and subtitle coverage.

Run from any directory: .venv/bin/python eda_full_scan.py
Does not change features, labels, splits or checkpoints.
"""
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'moment_detr'
OUT = ROOT / 'runs/eda'


def distribution(values):
    a = np.asarray(values, dtype=np.float64)
    return dict(zip(('min', 'p25', 'median', 'p75', 'p95', 'max'),
                    map(float, np.percentile(a, [0, 25, 50, 75, 95, 100])))) if a.size else {}


def inspect(path, expected):
    issues, stats = [], {}
    try:
        with np.load(path, allow_pickle=False) as data:
            if set(data.files) != set(expected):
                issues.append('unexpected_array_keys')
            for key in data.files:
                a = data[key]
                if not np.issubdtype(a.dtype, np.number) or np.iscomplexobj(a):
                    issues.append(f'{key}:unexpected_dtype')
                    continue
                nonfinite = int((~np.isfinite(a)).sum())
                zero_vectors = int(np.all(a == 0, axis=-1).sum()) if a.ndim else int(a == 0)
                shape_ok = key in expected and a.ndim == expected[key][0] and a.shape[-1] == expected[key][1]
                for condition, label in ((nonfinite > 0, 'nonfinite'), (a.size == 0, 'empty'),
                                         (not shape_ok, 'unexpected_shape'), (zero_vectors > 0, 'zero_vectors')):
                    if condition:
                        issues.append(f'{key}:{label}')
                stats[key] = {'shape': str(tuple(a.shape)), 'dtype': str(a.dtype),
                              'nonfinite': nonfinite, 'zero_vectors': zero_vectors}
    except Exception as exc:
        issues.append(f'unreadable:{type(exc).__name__}:{exc}')
    return issues, stats


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    started = time.time()
    schemas = {
        'clip_features': {'features': (2, 512)},
        'clip_sub_features': {'last_hidden_state': (2, 512), 'pooler_output': (1, 512)},
        'clip_text_features': {'last_hidden_state': (2, 512), 'pooler_output': (1, 512)},
        'slowfast_features': {'features': (2, 2304)},
    }
    report = {'feature_directories': {}, 'splits': {}, 'limitations': [
        'Integrity checks cover every NPZ in the four source feature directories.',
        'Subtitle absence means no matching feature file, not proven absence of speech.',
        'Derived-array alignment is checked against normalized query embeddings in annotation order; duplicate query text can still be ambiguous.',
        'Labels are generated proxies, not independently annotated modality importance.',
        'Saliency counts count individual ratings on annotated relevant clips, not all video clips.',
    ]}
    subtitle_counts = Counter()
    with (OUT / 'feature_issues.jsonl').open('w') as issue_file:
        for folder, schema in schemas.items():
            paths = sorted((SOURCE / 'features' / folder).glob('*.npz'))
            summary = {'files': len(paths), 'files_with_issues': 0, 'issue_counts': Counter(), 'arrays': {}}
            for i, path in enumerate(paths, 1):
                if folder == 'clip_sub_features' and path.stem.startswith('qid'):
                    subtitle_counts[path.stem[3:].rsplit('_subs', 1)[0]] += 1
                issues, stats = inspect(path, schema)
                if issues:
                    summary['files_with_issues'] += 1
                    summary['issue_counts'].update(issues)
                    issue_file.write(json.dumps({'file': str(path.relative_to(SOURCE)), 'issues': issues})+'\n')
                for key, stat in stats.items():
                    total = summary['arrays'].setdefault(key, {'shapes': Counter(), 'dtypes': Counter(), 'nonfinite_values': 0, 'zero_vectors': 0})
                    total['shapes'][stat['shape']] += 1
                    total['dtypes'][stat['dtype']] += 1
                    total['nonfinite_values'] += stat['nonfinite']
                    total['zero_vectors'] += stat['zero_vectors']
                if i % 10000 == 0:
                    print(f'{folder}: {i}/{len(paths)}; issue files={summary["files_with_issues"]}', flush=True)
            report['feature_directories'][folder] = summary
            print(f'{folder}: complete ({len(paths)} files)', flush=True)
    for split in ('train', 'val'):
        rows = [json.loads(line) for line in (SOURCE / f'data/highlight_{split}_release.jsonl').read_text().splitlines() if line.strip()]
        with np.load(ROOT / f'data/qvhighlights_{split}.npz', allow_pickle=False) as archive:
            embeddings = archive['query_embs']
            scores = archive['modality_scores']
            labels = archive['soft_labels']
        aligned = len(rows) == len(embeddings) == len(scores) == len(labels)
        mismatches = []
        if aligned:
            for i, row in enumerate(rows):
                with np.load(SOURCE / f"features/clip_text_features/qid{row['qid']}.npz", allow_pickle=False) as source:
                    emb = source['pooler_output'].astype(np.float32).reshape(-1)
                emb = emb / (np.linalg.norm(emb) + 1e-8)
                if not np.allclose(embeddings[i], emb, atol=1e-6, rtol=1e-5):
                    mismatches.append(row['qid'])
            aligned = not mismatches
        groups = {}
        for present in (True, False):
            indices = [i for i, r in enumerate(rows) if bool(subtitle_counts[r['vid']]) == present]
            selected = [rows[i] for i in indices]
            group = {'queries': len(indices), 'percent': 100*len(indices)/len(rows),
                     'unique_video_segments': len({r['vid'] for r in selected}),
                     'query_word_count': distribution([len(r['query'].split()) for r in selected]),
                     'window_duration_seconds': distribution([b-a for r in selected for a,b in r['relevant_windows']])}
            if aligned and indices:
                group['derived_dominant_labels'] = dict(zip(('visual', 'speech', 'ocr'), map(int, np.bincount(labels[indices].argmax(axis=1), minlength=3))))
                group['mean_derived_scores_visual_speech_ocr'] = scores[indices].mean(axis=0).astype(float).tolist()
            groups['with_subtitles' if present else 'without_subtitles'] = group
        missing = [{'qid': r['qid'], 'vid': r['vid'], 'query': r['query']} for r in rows if not subtitle_counts[r['vid']]]
        (OUT / f'missing_subtitles_{split}.json').write_text(json.dumps(missing, indent=2)+'\n')
        report['splits'][split] = {
            'queries': len(rows), 'derived_alignment_verified': aligned, 'mismatched_qids': mismatches,
            'subtitle_groups': groups,
            'video_duration_seconds': distribution([r['duration'] for r in rows]),
            'window_duration_seconds': distribution([b-a for r in rows for a,b in r['relevant_windows']]),
            'windows_per_query': distribution([len(r['relevant_windows']) for r in rows]),
            'queries_per_video_segment': distribution(list(Counter(r['vid'] for r in rows).values())),
            'subtitle_files_per_annotated_video_segment': distribution([subtitle_counts[v] for v in {r['vid'] for r in rows}]),
            'saliency_rating_counts': Counter(str(s) for r in rows for ratings in r['saliency_scores'] for s in ratings),
        }
    report['elapsed_seconds'] = round(time.time()-started, 2)
    (OUT / 'full_source_scan.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'elapsed_seconds': report['elapsed_seconds'], 'splits': report['splits']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
