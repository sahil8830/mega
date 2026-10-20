"""Inventory source features and audit all local train/validation annotations."""
import json
from collections import Counter
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'moment_detr'

def main():
    inventories = {}
    files = {}
    for directory in sorted((SOURCE / 'features').iterdir()):
        if not directory.is_dir():
            continue
        paths = sorted(directory.glob('*.npz'))
        files[directory.name] = {p.stem for p in paths}
        examples = []
        # Inspect a deterministic sample, not every feature archive.
        for p in paths[:3]:
            with np.load(p, allow_pickle=False) as archive:
                examples.append({'file': p.name, 'arrays': {
                    k: {'shape': list(archive[k].shape), 'dtype': str(archive[k].dtype),
                        'nonfinite_values': int((~np.isfinite(archive[k])).sum())}
                    for k in archive.files}})
        inventories[directory.name] = {'npz_files': len(paths), 'sampled_archives': examples}
    subtitle_vids = {s[3:].rsplit('_subs', 1)[0] for s in files['clip_sub_features'] if s.startswith('qid')}
    splits = {}
    rows = {}
    for split in ('train', 'val'):
        records = [json.loads(line) for line in (SOURCE / f'data/highlight_{split}_release.jsonl').read_text().splitlines() if line.strip()]
        rows[split] = records
        vids = {r['vid'] for r in records}
        durations = np.array([r['duration'] for r in records])
        lengths = [end-start for r in records for start, end in r['relevant_windows']]
        invalid_windows = sum(not (0 <= start < end <= r['duration']) for r in records for start, end in r['relevant_windows'])
        splits[split] = {
            'queries': len(records), 'unique_video_segments': len(vids),
            'unique_source_video_ids': len({v.rsplit('_', 2)[0] for v in vids}),
            'annotation_fields': sorted(set().union(*(r.keys() for r in records))),
            'duplicate_qids': len(records)-len({r['qid'] for r in records}),
            'repeated_normalized_queries_beyond_first': len(records)-len({r['query'].strip().lower() for r in records}),
            'empty_queries': sum(not r['query'].strip() for r in records),
            'invalid_windows': invalid_windows,
            'empty_window_lists': sum(not r['relevant_windows'] for r in records),
            'saliency_length_mismatches': sum(len(r['relevant_clip_ids']) != len(r['saliency_scores']) for r in records),
            'duration_seconds': {'min': float(durations.min()), 'median': float(np.median(durations)), 'max': float(durations.max())},
            'window_seconds': {'min': float(min(lengths)), 'median': float(np.median(lengths)), 'max': float(max(lengths))},
            'saliency_rating_counts': dict(sorted(Counter(str(s) for r in records for scores in r['saliency_scores'] for s in scores).items())),
            'missing_clip_visual_queries': sum(r['vid'] not in files['clip_features'] for r in records),
            'missing_slowfast_queries': sum(r['vid'] not in files['slowfast_features'] for r in records),
            'missing_query_features': sum(f"qid{r['qid']}" not in files['clip_text_features'] for r in records),
            'queries_without_subtitle_files': sum(r['vid'] not in subtitle_vids for r in records),
        }
    overlap = {}
    for name, key in [('qid', lambda r:r['qid']), ('video_segment', lambda r:r['vid']),
                      ('source_video', lambda r:r['vid'].rsplit('_',2)[0]),
                      ('normalized_query', lambda r:r['query'].strip().lower())]:
        overlap[name] = len({key(r) for r in rows['train']} & {key(r) for r in rows['val']})
    report = {'source': str(SOURCE / 'features'), 'feature_inventory': inventories,
              'splits': splits, 'train_val_overlap': overlap,
              'limitations': ['Feature values inspected in only the first three sorted archives per directory; coverage checks use all filenames.',
                              'Source annotations provide temporal windows and saliency, not visual/speech/OCR class labels.',
                              'Feature directory counts include files outside the local train/validation annotation coverage.',
                              'Source video identity inferred by removing the final two underscore-separated timestamp fields.']}
    out = ROOT / 'runs/eda/source_dataset_audit.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
