# Short EDA Report

## Dataset

We analysed the QVHighlights source dataset stored in
`mega/moment_detr/features` together with its train and validation annotations.

| Item | Result |
| --- | ---: |
| Training queries | 7,218 |
| Validation queries | 1,550 |
| Unique training video segments | 7,100 |
| Unique validation video segments | 1,519 |
| CLIP visual feature files | 12,562 |
| SlowFast feature files | 12,562 |
| CLIP query feature files | 10,310 |
| Subtitle feature files | 329,745 |

The features represent video appearance, motion, query meaning, and subtitle
meaning as numerical vectors. Train and validation have no overlapping query
IDs, video segments, or source videos.

## Data-quality results

All 365,179 feature archives were scanned. No corrupt files, NaN/infinite
values, empty arrays, unexpected feature dimensions, or all-zero vectors were
found. The source feature data is numerically healthy.

No empty queries, duplicate query IDs, invalid relevant windows, or mismatched
saliency annotations were found. The typical video duration is 150 seconds and
the median relevant-moment duration is 16 seconds.

## Subtitle coverage

| Split | With subtitle features | Without subtitle features |
| --- | ---: | ---: |
| Training | 5,486 (76.00%) | 1,732 (24.00%) |
| Validation | 1,212 (78.19%) | 338 (21.81%) |

Missing subtitle features do not necessarily mean that a video has no speech.

## Class-balance and label-quality results

QVHighlights does not contain visual, speech, and OCR class labels. The project
generated these proxy labels from modality scores.

| Generated class | Training | Validation |
| --- | ---: | ---: |
| Visual | 1,759 (24.37%) | 343 (22.13%) |
| Speech | 5,459 (75.63%) | 1,207 (77.87%) |
| OCR | 0 | 0 |

The generated labels have a strong subtitle-availability bias:

- 5,459 of 5,486 subtitle-available training queries were labeled speech.
- All 1,732 subtitle-missing training queries were labeled visual.
- No query received an OCR-dominant label.

A separate 100-query Codex-assisted review based on query meaning found 51
visual, 22 speech, 3 OCR, and 24 mixed queries. Compared with that review, the
generated labels achieved 40.00% exact agreement, 52.63% three-class accuracy,
30.75% macro F1, and 0% OCR recall. This is a diagnostic review based on query
text; it is not a human or raw-video evidence benchmark.

Therefore, balancing the current generated labels would repeat their bias.
Oversampling cannot create valid OCR examples or correct unreliable labels.

## Valid retrieval baseline

The checked-in Moment-DETR predictions were evaluated again on all 1,550
validation queries with the official local evaluator.

| Metric | Result |
| --- | ---: |
| Moment retrieval R@1 at IoU 0.5 | 53.23% |
| Moment retrieval R@1 at IoU 0.7 | 34.00% |
| Moment retrieval mAP | 30.58% |
| Short-moment mAP | 3.11% |
| Middle-moment mAP | 29.42% |
| Long-moment mAP | 41.27% |
| Highlight Fair mAP | 68.29% |

The main performance weakness is retrieval of short moments. The previously
reported 99.74% value measures agreement with generated modality labels; it is
not end-to-end video-retrieval accuracy.

## EDA conclusion

The source feature files are complete and numerically valid. The main issue is
the construction and imbalance of the generated modality labels. The next
experiments should use the native temporal-window and saliency annotations,
preserve the current retrieval baseline, and target short-moment retrieval.
