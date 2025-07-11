import csv
import sys
import json
import argparse
from collections import defaultdict

def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Evaluate DOI matching results using Precision, Recall, and F-beta scores."
    )
    parser.add_argument(
        "-d", "--test_data_json",
        required=True,
        help="Path to the JSON test data file containing inputs and ground-truth outputs."
    )
    parser.add_argument(
        "-r", "--results_json",
        required=True,
        help="Path to the test results JSON file generated by the matching script."
    )
    parser.add_argument(
        "-c", "--output_csv",
        help="Optional path to save the summary evaluation metrics to a CSV file."
    )
    parser.add_argument(
        "--details_csv",
        help="Optional path to save a detailed breakdown of TP, FP, and FN results to a CSV file."
    )
    parser.add_argument(
        "--json-output",
        action='store_true',
        help="If set, print evaluation metrics as a JSON object to stdout and suppress other console output."
    )
    return parser.parse_args()


def load_reference_from_json(file_path, suppress_errors=False):
    reference_dict = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as infile:
            data = json.load(infile)
            if 'items' not in data or not isinstance(data['items'], list):
                if not suppress_errors:
                    print(f"Error: JSON file {file_path} must contain a top-level 'items' list.", file=sys.stderr)
                return None

            for item in data['items']:
                try:
                    input_data = json.loads(item.get('input', '{}'))
                    source_doi = input_data.get('DOI')
                    if not source_doi:
                        continue
                    
                    source_doi = source_doi.strip().lower()

                    related_dois_list = item.get('output', [])
                    
                    valid_doi_set = set()
                    if related_dois_list and isinstance(related_dois_list, list):
                        for doi_url in related_dois_list:
                            if doi_url and isinstance(doi_url, str):
                                doi_path = doi_url.replace("https://doi.org/", "").replace("doi:", "").strip()
                                if doi_path:
                                    valid_doi_set.add(doi_path.lower())
                    
                    if source_doi:
                         reference_dict[source_doi] = valid_doi_set

                except (json.JSONDecodeError, KeyError) as e:
                    if not suppress_errors:
                        print(f"Warning: Skipping item due to parsing error in {file_path}: {e}", file=sys.stderr)
                    continue
    except FileNotFoundError:
        if not suppress_errors:
            print(f"Error: File not found: {file_path}", file=sys.stderr)
        return None
    except Exception as e:
        if not suppress_errors:
            print(f"Error reading JSON file {file_path}: {e}", file=sys.stderr)
        return None
    return reference_dict


def load_results_from_json(file_path, suppress_errors=False):
    results_dict = {}
    try:
        with open(file_path, 'r', encoding='utf-8') as infile:
            data = json.load(infile)
            if not isinstance(data, list):
                if not suppress_errors:
                    print(f"Error: Results JSON file {file_path} must contain a top-level list.", file=sys.stderr)
                return None

            for item in data:
                key = item.get('input_doi')
                value = item.get('matched_doi')
                if key:
                    key = key.strip().lower()
                    value = value.strip().lower() if value else None
                    results_dict[key] = value

    except FileNotFoundError:
        if not suppress_errors:
            print(f"Error: File not found: {file_path}", file=sys.stderr)
        return None
    except Exception as e:
        if not suppress_errors:
            print(f"Error reading JSON file {file_path}: {e}", file=sys.stderr)
        return None
    return results_dict


def calculate_f_beta(precision, recall, beta):
    if precision == 0.0 and recall == 0.0:
        return 0.0
    if beta <= 0:
        raise ValueError("Beta must be a positive number.")

    beta_sq = beta ** 2
    numerator = (1 + beta_sq) * (precision * recall)
    denominator = (beta_sq * precision) + recall

    if denominator == 0:
        return 0.0
    return numerator / denominator


def calculate_metrics(reference_map, test_map):
    tp = 0
    fp = 0
    fn = 0
    detailed_results = []

    positive_references = {k: v for k, v in reference_map.items() if v}
    num_positive_references = len(positive_references)

    positive_predictions = 0

    all_input_dois = set(reference_map.keys()) | set(test_map.keys())

    for input_doi in sorted(list(all_input_dois)):
        input_doi_norm = input_doi.strip().lower()
        
        predicted_match = test_map.get(input_doi_norm)
        is_positive_prediction = bool(predicted_match)

        correct_match_set = positive_references.get(input_doi_norm)
        is_in_ref = bool(correct_match_set)

        detail_record = {
            "input_doi": input_doi_norm,
            "predicted_doi": predicted_match or "",
            "reference_doi": " | ".join(sorted(list(correct_match_set))) if correct_match_set else "",
            "status": ""
        }

        if is_positive_prediction:
            positive_predictions += 1
            if is_in_ref:
                if predicted_match in correct_match_set:
                    tp += 1
                    detail_record["status"] = "TP"
                else:
                    fp += 1
                    detail_record["status"] = "FP"
            else:
                fp += 1
                detail_record["status"] = "FP"
        else:
            if is_in_ref:
                fn += 1
                detail_record["status"] = "FN"
        
        if detail_record["status"]:
            detailed_results.append(detail_record)

    precision = tp / positive_predictions if positive_predictions > 0 else 0.0
    recall = tp / num_positive_references if num_positive_references > 0 else 0.0

    f0_5 = calculate_f_beta(precision, recall, 0.5)
    f1 = calculate_f_beta(precision, recall, 1.0)
    f1_5 = calculate_f_beta(precision, recall, 1.5)

    metrics = {
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "Precision": precision,
        "Recall": recall,
        "F0.5": f0_5,
        "F1": f1,
        "F1.5": f1_5,
        "Positive References": num_positive_references,
        "Positive Predictions": positive_predictions
    }
    
    return metrics, detailed_results


def write_summary_to_csv(metrics, output_file, suppress_print=False):
    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            fieldnames = [
                "Positive References", "Positive Predictions",
                "TP", "FP", "FN",
                "Precision", "Recall",
                "F0.5", "F1", "F1.5"
            ]
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            formatted_metrics = {k: (f"{v:.4f}" if isinstance(v, float) else v)
                                 for k, v in metrics.items() if k in fieldnames}
            writer.writerow(formatted_metrics)
        if not suppress_print:
            print(f"\nSummary metrics saved to: {output_file}")
    except IOError as e:
        if not suppress_print:
            print(f"Error writing summary metrics to CSV file {output_file}: {e}", file=sys.stderr)

def write_details_to_csv(detailed_results, output_file, suppress_print=False):
    try:
        with open(output_file, 'w', encoding='utf-8') as outfile:
            fieldnames = ["input_doi", "predicted_doi", "reference_doi", "status"]
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(detailed_results)
        if not suppress_print:
            print(f"Detailed results saved to: {output_file}")
    except IOError as e:
        if not suppress_print:
            print(f"Error writing detailed results to CSV file {output_file}: {e}", file=sys.stderr)


def main():
    args = parse_arguments()
    suppress_console = args.json_output

    if not suppress_console:
        print(f"Loading reference data from: {args.test_data_json}")
    reference_data = load_reference_from_json(args.test_data_json, suppress_errors=suppress_console)
    if reference_data is None:
        if not suppress_console:
            print("Failed to load reference data. Exiting.", file=sys.stderr)
            sys.exit(1)
        else:
            print(json.dumps({"error": f"Failed to load reference JSON: {args.test_data_json}"}), file=sys.stdout)
            sys.exit(1)

    if not suppress_console:
        print(f"Loading test results from: {args.results_json}")
    test_data = load_results_from_json(
        args.results_json, suppress_errors=suppress_console)
    if test_data is None:
        if not suppress_console:
            print("Failed to load test results. Exiting.", file=sys.stderr)
            sys.exit(1)
        else:
            print(json.dumps({"error": f"Failed to load results JSON: {args.results_json}"}), file=sys.stdout)
            sys.exit(1)

    if not suppress_console:
        print("\nCalculating metrics...")
    
    metrics, detailed_results = calculate_metrics(reference_data, test_data)

    if args.json_output:
        print(json.dumps(metrics, indent=None))
    else:
        print("\n--- Evaluation Results ---")
        print(f"Positive Relations in Reference: {metrics['Positive References']}")
        print(f"Positive Predictions in Test:    {metrics['Positive Predictions']}")
        print(f"True Positives (TP):  {metrics['TP']}")
        print(f"False Positives (FP): {metrics['FP']}")
        print(f"False Negatives (FN): {metrics['FN']}")
        print("--------------------------")
        print(f"Precision: {metrics['Precision']:.4f}")
        print(f"Recall:    {metrics['Recall']:.4f}")
        print("--------------------------")
        print(f"F0.5 Score (Prec > Rec): {metrics['F0.5']:.4f}")
        print(f"F1 Score   (Balanced):   {metrics['F1']:.4f}")
        print(f"F1.5 Score (Rec > Prec): {metrics['F1.5']:.4f}")
        print("--------------------------")

    if args.output_csv:
        write_summary_to_csv(metrics, args.output_csv, suppress_print=suppress_console)
    
    if args.details_csv:
        write_details_to_csv(detailed_results, args.details_csv, suppress_print=suppress_console)


if __name__ == "__main__":
    main()