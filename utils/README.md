# Calculate Precision, Recall, and F-scores

Calculates precision, recall, and f-scores for preprint matching results.

## Usage

```bash
python calculate_precision_recall_f-scores.py -d test_data.json -r results.json
```

## Arguments

- `-d, --test_data_json`: Ground truth test data (JSON)
- `-r, --results_json`: Test results from matching script (JSON)
- `-c, --output_csv`: Save summary metrics to CSV
- `--details_csv`: Save detailed TP/FP/FN breakdown to CSV
- `--json-output`: Output metrics as JSON to stdout

## Output

Displays TP/FP/FN counts, precision, recall, and F-scores (F0.5, F1, F1.5).