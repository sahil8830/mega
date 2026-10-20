# Dataset balancing decision

## Decision

Do not balance or retrain the modality-weighting model with the current proxy
labels. The dominant label is largely determined by whether subtitle feature
files exist, and OCR has no dominant training or validation examples. Random
oversampling would repeat this bias rather than repair it.

## Evidence

The full source scan found no corrupt or numerically invalid feature archives,
so file integrity is not the cause. In the complete generated training arrays:

- 5,459 of 5,486 subtitle-available queries are labeled speech.
- All 1,732 subtitle-missing queries are labeled visual.
- No training query is labeled OCR.

A separate Codex-assisted review of 100 stratified validation queries used only
query meaning and was explicitly marked as non-human and non-video evidence. It
found 51 visual, 22 speech, 3 OCR, and 24 mixed queries. Against this review, the
current proxy labels achieved:

- Exact five-label agreement: 40.00%
- Three-class accuracy, excluding mixed cases: 52.63%
- Macro F1: 30.75%
- OCR recall: 0.00%
- Agreement with subtitles available: 30.00%
- Agreement with subtitles missing: 55.00%

These figures are a diagnostic of label construction, not a final benchmark.
Raw videos are unavailable for 99 of the 100 sampled queries, so the review
cannot verify which evidence actually occurs within each relevant moment.

## Valid baseline for the native dataset task

The checked-in Moment-DETR validation predictions were rerun with the official
local evaluator over all 1,550 validation queries. The reproducible baseline is:

| Metric | Value |
| --- | ---: |
| Moment retrieval R@1, IoU 0.5 | 53.23% |
| Moment retrieval R@1, IoU 0.7 | 34.00% |
| Moment retrieval mean AP | 30.58% |
| Highlight Fair mean AP | 68.29% |
| Highlight Good mean AP | 57.93% |
| Highlight VeryGood mean AP | 35.51% |

Short moments are the weakest group at 3.11% moment-retrieval mean AP, compared
with 29.42% for middle and 41.27% for long moments.

## Next implementation step

Use QVHighlights' temporal-window and saliency annotations for end-to-end
retrieval evaluation. Keep the above validation numbers as the unchanged
baseline. Before modality-weight model retraining, obtain either independently
annotated modality labels with raw-video access or define a weak-supervision
method whose labels do not encode subtitle availability. Any resampling must be
applied only to the training split after that label set exists.

For hyperparameter experiments, record one change per run and compare moment
retrieval R@1 at IoU 0.5/0.7 and mAP. Do not call proxy-label accuracy retrieval
accuracy, and do not use the final test split for tuning.

## Artifacts

- `modality_label_audit.tsv`: blank sheet for an independent human reviewer.
- `modality_label_audit_codex.tsv`: completed query-text-only assisted review.
- `modality_label_audit_codex_results.json`: assisted-review metrics.
- `moment_detr_validation_baseline.json`: rerun native-task baseline metrics.
