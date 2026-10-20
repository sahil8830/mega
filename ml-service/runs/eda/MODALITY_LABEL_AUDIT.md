# Modality label audit

The audit sheet contains 100 deterministic validation queries. It includes all
13 OCR-only cue candidates and samples visual, speech, mixed, and no-keyword
queries. Sampling represents both videos with subtitle feature files and videos
without them where the source data permits.

Fill only these columns in `modality_label_audit.tsv`:

- `human_label`: `visual`, `speech`, `ocr`, `mixed`, or `unclear`.
- `human_confidence`: `high`, `medium`, or `low`.
- `reviewer_notes`: short reason for difficult or mixed cases.

Use these definitions:

- `visual`: the requested moment is identified mainly by objects, actions, people, or scenes.
- `speech`: it is identified mainly by what is spoken.
- `ocr`: it is identified mainly by readable text inside the video frame.
- `mixed`: two or more modalities are materially necessary.
- `unclear`: the query does not provide enough information for a reliable judgment.

Judge the query intent independently. Do not copy `cue_bucket`, `proxy_label`,
or the numerical scores. Those columns are included for analysis after labeling.
The source checkout contains only one raw example video, so this first audit
measures query-intent label quality rather than verifying evidence inside all
video moments. A full evidence audit requires the corresponding raw videos.

`modality_label_audit_codex.tsv` is a separate, completed Codex-assisted review.
Its labels are based only on the query text and are not represented as human
annotations. The original blank sheet is preserved for an independent reviewer.

Generate the same sheet:

```bash
cd mega/ml-service
.venv/bin/python create_modality_label_audit.py
```

After all 100 rows are labeled, calculate agreement, per-class precision and
recall, macro F1, confusion matrix, and agreement by subtitle availability:

```bash
.venv/bin/python evaluate_modality_label_audit.py
```

To inspect progress before completion:

```bash
.venv/bin/python evaluate_modality_label_audit.py --allow-incomplete
```
