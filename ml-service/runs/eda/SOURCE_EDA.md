# Full source dataset EDA

Source: `mega/moment_detr/features` and the local train/validation annotation files.

## Full numerical scan

| Directory | NPZ files scanned | Files with issues |
| --- | ---: | ---: |
| clip_features | 12,562 | 0 |
| clip_sub_features | 329,745 | 0 |
| clip_text_features | 10,310 | 0 |
| slowfast_features | 12,562 | 0 |

Checks: archive readability, expected keys and dimensions, numeric dtypes, empty arrays, NaN/infinity, and all-zero feature vectors. File-level issues are in `feature_issues.jsonl`.

## Subtitle coverage and generated labels

| Split | Subtitle files | Queries | Visual label | Speech label | OCR label |
| --- | --- | ---: | ---: | ---: | ---: |
| train | with_subtitles | 5486 (76.00%) | 27 | 5459 | 0 |
| train | without_subtitles | 1732 (24.00%) | 1732 | 0 | 0 |
| val | with_subtitles | 1212 (78.19%) | 6 | 1206 | 0 |
| val | without_subtitles | 338 (21.81%) | 337 | 1 | 0 |

Derived labels were joined to annotations only after verifying normalized query embeddings against source query files in annotation order. Repeated queries remain ambiguous identifiers.

The generator uses maximum similarity over video-level subtitles when available. Without subtitles, it uses half of a query-keyword speech signal. OCR is also a query-keyword heuristic; visual similarity uses clips inside annotated relevant windows. These are different evidence sources and scopes, so their argmax should not be treated as human-annotated modality importance.

- train: 1732/1732 missing-subtitle speech scores match the keyword fallback; 1494 are zero.
- val: 338/338 missing-subtitle speech scores match the keyword fallback; 302 are zero.

Missing subtitle files do not prove that the videos have no speech.

## Distributions

| Split | Measure | Min | Median | P95 | Max |
| --- | --- | ---: | ---: | ---: | ---: |
| train | video_duration_seconds | 120 | 150 | 150 | 150 |
| train | window_duration_seconds | 2 | 16 | 88 | 150 |
| train | windows_per_query | 1 | 1 | 5 | 24 |
| train | queries_per_video_segment | 1 | 1 | 1 | 2 |
| train | subtitle_files_per_annotated_video_segment | 0 | 33 | 74 | 561 |
| val | video_duration_seconds | 120 | 150 | 150 | 150 |
| val | window_duration_seconds | 2 | 16 | 74 | 150 |
| val | windows_per_query | 1 | 1 | 5 | 25 |
| val | queries_per_video_segment | 1 | 1 | 1 | 2 |
| val | subtitle_files_per_annotated_video_segment | 0 | 34 | 75 | 543 |

Saliency counts below count individual annotator ratings on relevant clips, not classes of whole queries.

| Split | Rating 0 | Rating 1 | Rating 2 | Rating 3 | Rating 4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| train | 15594 | 34972 | 88925 | 147642 | 194586 |
| val | 3622 | 7859 | 18517 | 29268 | 38381 |

## Decision before balancing

Do not rebalance the source feature files to equal folder counts: feature folders represent different units (video clips, subtitle sentences, queries). Do not drop videos solely because subtitles are absent.

First audit a representative sample of visual-, speech-, and OCR-oriented queries with independent modality judgments, covering both subtitle-availability groups. Define whether the experiment targets modality prediction or end-to-end moment retrieval. The current generated labels do not supply an OCR-dominant class.

For retrieval, record Recall@K with temporal IoU and mAP using temporal annotations. For independently labeled modality prediction, record class counts, confusion matrix, per-class precision/recall and macro F1 alongside accuracy. Compare against fixed-weight and majority baselines where appropriate.

After the label audit, apply any balancing only to training examples. Tune on validation, record one change per experiment with a fixed seed and split, and reserve independent test data for the final result.

Existing 99.74% modality-label validation accuracy measures agreement with generated proxy labels. It is not end-to-end retrieval accuracy, and that validation split was used for checkpoint selection.

## Artifacts

- `full_source_scan.json`: complete numerical and distribution results.
- `feature_issues.jsonl`: all flagged feature files (empty if none).
- `missing_subtitles_train.json`, `missing_subtitles_val.json`: affected query identities.
- `subtitle_fallback_audit.json`: comparison with the current fallback rule.

Reproduce the full scan with `mega/ml-service/.venv/bin/python mega/ml-service/eda_full_scan.py`. Then run `mega/ml-service/.venv/bin/python mega/ml-service/eda_subtitle_fallback.py` to audit the fallback. Render this report with `mega/ml-service/.venv/bin/python mega/ml-service/eda_full_report.py`.
