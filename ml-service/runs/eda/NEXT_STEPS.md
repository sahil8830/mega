# What To Do Next

## 1. Preserve the baseline

Keep `moment_detr_validation_baseline.json` unchanged. For every experiment,
record the configuration and compare these primary metrics:

- Moment retrieval R@1 at IoU 0.5
- Moment retrieval R@1 at IoU 0.7
- Overall moment retrieval mAP
- Short-, middle-, and long-moment mAP

Do not use the 99.74% proxy-label accuracy as retrieval accuracy.

## 2. Define the evaluation split correctly

Use training data for fitting and validation data for hyperparameter selection.
Do not repeatedly tune on the final test split. Use fixed random seeds and keep
video-level separation between splits to avoid leakage.

The current validation set was already used for checkpoint selection. Final
reported performance will require an untouched test set or a new held-out split.

## 3. Do not balance the current proxy labels

Do not oversample visual examples or duplicate speech/OCR examples from the
current generated arrays. OCR has zero dominant examples, and label choice is
strongly linked to subtitle-file availability.

Before retraining the modality-weighting classifier, choose one of these paths:

1. Obtain raw videos and independently annotate visual, speech, OCR, mixed, and
   unclear evidence for a representative set of queries.
2. Redesign weak-label generation so visual, speech, and OCR scores use evidence
   from the same relevant time window and missing modalities are represented by
   availability masks instead of fallback scores.

Only after label quality is verified should class weighting, weighted sampling,
or focal loss be tested on the training split.

## 4. Run controlled retrieval experiments

Start with one change per experiment. Recommended order:

| Experiment | Change | Purpose |
| --- | --- | --- |
| E0 | Existing checkpoint and configuration | Fixed baseline |
| E1 | Increase temporal resolution or use shorter clips | Improve short moments |
| E2 | Tune number of moment queries | Improve proposal coverage |
| E3 | Tune learning rate | Improve optimization |
| E4 | Tune saliency-loss weight | Balance retrieval and highlight learning |
| E5 | Tune moment-retrieval loss weights | Improve temporal boundaries |
| E6 | Add subtitle-availability masks | Prevent missing-data bias |

Change only one setting from E0 at a time. Keep the same split, seed, epochs,
and evaluation command so the comparison remains fair.

## 5. Record every result

Create one row per experiment with these columns:

| Run | Single change | R@1@0.5 | R@1@0.7 | mAP | Short mAP | Middle mAP | Long mAP | Notes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| E0 | Baseline | 53.23 | 34.00 | 30.58 | 3.11 | 29.42 | 41.27 | Existing checkpoint |

Save the exact command, configuration, checkpoint, random seed, runtime, and
metrics JSON for every run. A change should be accepted only if it improves the
chosen primary metric without causing a major regression in other groups.

## 6. Evaluate the final configuration once

After choosing hyperparameters using validation results, train the selected
configuration and evaluate it once on untouched test data. Report retrieval
R@1, mAP, duration-group results, highlight mAP, and any limitations.

## Useful commands

Reproduce the current validation baseline:

```bash
cd mega/moment_detr
PYTHONPATH=. ../ml-service/.venv/bin/python standalone_eval/eval.py \
  --submission_path run_on_video/moment_detr_ckpt/inference_hl_val_test_code_preds.jsonl \
  --gt_path data/highlight_val_release.jsonl \
  --save_path ../ml-service/runs/eda/moment_detr_validation_baseline.json
```

Recreate and evaluate the query-intent audit:

```bash
cd mega/ml-service
.venv/bin/python create_modality_label_audit.py
.venv/bin/python apply_codex_query_intent_audit.py
.venv/bin/python evaluate_modality_label_audit.py \
  runs/eda/modality_label_audit_codex.tsv \
  --output runs/eda/modality_label_audit_codex_results.json
```
