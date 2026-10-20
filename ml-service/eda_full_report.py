"""Render completed full-source EDA results as a readable Markdown report."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'runs/eda'


def main():
    report = json.loads((OUT / 'full_source_scan.json').read_text())
    fallback = json.loads((OUT / 'subtitle_fallback_audit.json').read_text())
    lines = ['# Full source dataset EDA', '',
             'Source: `mega/moment_detr/features` and the local train/validation annotation files.', '',
             '## Full numerical scan', '',
             '| Directory | NPZ files scanned | Files with issues |',
             '| --- | ---: | ---: |']
    for name, result in report['feature_directories'].items():
        lines.append(f"| {name} | {result['files']:,} | {result['files_with_issues']:,} |")
    lines += ['', 'Checks: archive readability, expected keys and dimensions, numeric dtypes, empty arrays, '
              'NaN/infinity, and all-zero feature vectors. File-level issues are in `feature_issues.jsonl`.', '',
              '## Subtitle coverage and generated labels', '',
              '| Split | Subtitle files | Queries | Visual label | Speech label | OCR label |',
              '| --- | --- | ---: | ---: | ---: | ---: |']
    for split, data in report['splits'].items():
        for name, group in data['subtitle_groups'].items():
            labels = group.get('derived_dominant_labels', {})
            lines.append(f"| {split} | {name} | {group['queries']} ({group['percent']:.2f}%) | " +
                         ' | '.join(str(labels.get(k, 'unverified')) for k in ('visual', 'speech', 'ocr')) + ' |')
    lines += ['', 'Derived labels were joined to annotations only after verifying normalized query embeddings '
              'against source query files in annotation order. Repeated queries remain ambiguous identifiers.', '',
              'The generator uses maximum similarity over video-level subtitles when available. Without subtitles, '
              'it uses half of a query-keyword speech signal. OCR is also a query-keyword heuristic; visual similarity '
              'uses clips inside annotated relevant windows. These are different evidence sources and scopes, so '
              'their argmax should not be treated as human-annotated modality importance.', '']
    for split, data in fallback.items():
        lines.append(f"- {split}: {data['speech_fallback_match_count']}/{data['missing_subtitle_queries']} missing-subtitle "
                     f"speech scores match the keyword fallback; {data['zero_speech_fallback_count']} are zero.")
    lines += ['', 'Missing subtitle files do not prove that the videos have no speech.', '',
              '## Distributions', '',
              '| Split | Measure | Min | Median | P95 | Max |',
              '| --- | --- | ---: | ---: | ---: | ---: |']
    for split, data in report['splits'].items():
        for key in ('video_duration_seconds', 'window_duration_seconds', 'windows_per_query',
                    'queries_per_video_segment', 'subtitle_files_per_annotated_video_segment'):
            d = data[key]
            lines.append(f"| {split} | {key} | " + ' | '.join(f'{d[k]:g}' for k in ('min','median','p95','max')) + ' |')
    lines += ['', 'Saliency counts below count individual annotator ratings on relevant clips, not classes of whole queries.', '',
              '| Split | Rating 0 | Rating 1 | Rating 2 | Rating 3 | Rating 4 |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for split, data in report['splits'].items():
        lines.append(f'| {split} | ' + ' | '.join(str(data['saliency_rating_counts'].get(str(i), 0)) for i in range(5)) + ' |')
    lines += ['', '## Decision before balancing', '',
              'Do not rebalance the source feature files to equal folder counts: feature folders represent different '
              'units (video clips, subtitle sentences, queries). Do not drop videos solely because subtitles are absent.', '',
              'First audit a representative sample of visual-, speech-, and OCR-oriented queries with independent '
              'modality judgments, covering both subtitle-availability groups. Define whether the experiment targets '
              'modality prediction or end-to-end moment retrieval. The current generated labels do not supply an OCR-dominant class.', '',
              'For retrieval, record Recall@K with temporal IoU and mAP using temporal annotations. For independently '
              'labeled modality prediction, record class counts, confusion matrix, per-class precision/recall and macro F1 '
              'alongside accuracy. Compare against fixed-weight and majority baselines where appropriate.', '',
              'After the label audit, apply any balancing only to training examples. Tune on validation, record one '
              'change per experiment with a fixed seed and split, and reserve independent test data for the final result.', '',
              'Existing 99.74% modality-label validation accuracy measures agreement with generated proxy labels. '
              'It is not end-to-end retrieval accuracy, and that validation split was used for checkpoint selection.', '',
              '## Artifacts', '',
              '- `full_source_scan.json`: complete numerical and distribution results.',
              '- `feature_issues.jsonl`: all flagged feature files (empty if none).',
              '- `missing_subtitles_train.json`, `missing_subtitles_val.json`: affected query identities.',
              '- `subtitle_fallback_audit.json`: comparison with the current fallback rule.', '',
              'Reproduce the full scan with `mega/ml-service/.venv/bin/python mega/ml-service/eda_full_scan.py`. '
              'Then run `mega/ml-service/.venv/bin/python mega/ml-service/eda_subtitle_fallback.py` to audit the fallback. '
              'Render this report with `mega/ml-service/.venv/bin/python mega/ml-service/eda_full_report.py`.']
    (OUT / 'SOURCE_EDA.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    main()
