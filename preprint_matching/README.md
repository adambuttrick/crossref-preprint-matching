# **Crossref Preprint Matching**

Modified form of [Search Based Matching with Validation (SBMV) preprint matching strategy](https://gitlab.com/crossref/labs/marple/-/blob/main/strategies_available/preprint_sbmv/strategy.py?ref_type=heads) developed by [@dtkaczyk](https://github.com/dtkaczyk). 

This code is intended to evaluate the soundness of the strategy in [arxiv-preprint-matching](https://github.com/cometadata/arxiv-preprint-matching) by testing it against the benchmark dataset used in the original SBMV preprint matching strategy, where journal articles are matched to preprints in Crossref alone.


## **Installation**
```
pip install \-r requirements.txt
```
## **Usage**

The script processes a single JSON file containing a list of Crossref works, saving results to a specified output directory.

```
python preprint\_match\_data\_files.py \-i INPUT\_FILE \-f FORMAT \-m EMAIL \-u USER\_AGENT \[OPTIONS\]
```
### **Required Arguments**

* \-i, \--input: Path to a single JSON file containing Crossref works to be matched.  
* \-f, \--format: Output format ('json' or 'csv') for the result files.  
* \-m, \--mailto: Email address for Crossref API politeness (required by Crossref).  
* \-u, \--user-agent: User-Agent string for API requests (e.g., "arXivPreprintMatcher/1.0").

### **Optional Arguments**

#### **Input/Output:**

* \-o, \--output: Path to the output directory where results will be saved. Will be created if it doesn't exist (default: ./output).

#### **Logging:**

* \-ll, \--log-level: Set logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL, NONE). Default: INFO.  
* \-lf, \--log-file: Path to log file (defaults to stderr).  
* \-lc, \--log-candidates: If set, logs raw Crossref candidate results to the candidate log file.  
* \-cf, \--candidate-log-file: Path for logging candidates (default: crossref\_candidates.log).

#### **Strategy Parameters:**

* \--min-score: Minimum score threshold for a match (default: 0.85).  
* \--max-score-diff: Maximum allowed difference from top score for multiple matches (default: 0.03).  
* \--weight-year: Weight for the year score component (default: 0.4).  
* \--weight-title: Weight for the title score component (default: 2.0).  
* \--weight-author: Weight for the author score component (default: 0.8).  
* \--max-query-len: Maximum length of the query string sent to Crossref (default: 5000).

#### **File Processing & API Handling:**

* \--timeout: Request timeout (connect, read) in seconds (default: 10 30).  
* \--max-retries: Maximum number of retries for failed API requests (default: 3).  
* \--backoff-factor: Exponential backoff factor for retries (default: 0.5).  
* \--max-consecutive-line-failures: Maximum number of consecutive lines that fail processing within a single file before halting processing for that file (default: 10).  
* \--max-consecutive-file-failures: Maximum number of consecutive files that fail processing before halting the entire script (default: 3).

## **Examples**

Process a file input\_data/works\_to\_match.json and save CSV results to output\_results/:

```
python preprint\_match\_data\_files.py \-i input\_data/works\_to\_match.json \-o output\_results/ \-f csv \-m \<your\_email@example.com\> \-u "MyMatchingTool/1.1 (mailto:your\_email@example.com)"
```

Process a file preprints/crossref\_data.json, saving JSON results to the default ./output directory, with detailed logging and custom API/strategy settings:

```
python preprint\_match\_data\_files.py \-i preprints/crossref\_data.json \-f json \-m \<your\_email@example.com\> \-u "arXivPreprintMatcher/1.0" \\  
 \-ll DEBUG \-lf matching.log \-lc \\  
 \--min-score 0.8 \--weight-title 1.5 \--weight-author 1.0 \\  
 \--timeout 15 45 \--max-retries 5 \--max-consecutive-line-failures 20
```

## **Description of Strategy**

This strategy attempts to find potential preprint versions corresponding to input published works (expected in Crossref JSON format). It uses the Crossref API and applies scoring based on metadata similarity.

### **Search Approach and Candidate Filtering**

1. A bibliographic query string is built using metadata extracted from the input Crossref JSON: the main title (and subtitle, if present), publication year, and the family names of authors. These components are normalized using unidecode, lowercasing, and removing punctuation before constructing the query.  
2. The query targets the Crossref /works endpoint via a robust HTTP session, using the query.bibliographic parameter and returning up to 25 candidates. The maximum query length is capped (default 5000).  
3. Candidates retrieved from Crossref are filtered to include only preprints by accepting only works where the type field is posted-content.

### **Scoring Logic, Weights, and Heuristics:**

The strategy employs weighted scoring based on year, title, and author similarity, incorporating fuzzy matching and heuristics.

* **Year Score:**  
  * Compares the published article's year with the preprint candidate's year (extracted from fields like published-online, issued, etc.).  
  * Assigns scores based on the difference (article\_year \- preprint\_year): a score of 0.0 is given if the difference is negative (article published before preprint). A score of 1.0 is given for a difference of 0-2 years, 0.9 for 3 years, 0.8 for 4 years, and 0.0 for all larger differences. Returns 0.0 if years cannot be compared.  
* **Title Score:**  
  * Compares normalized titles. Normalization includes Unicode handling, accent removal, lowercasing, and punctuation stripping.  
  * Uses a weighted blend of fuzzy matching scores from the rapidfuzz library: 0.4 \* token\_set\_ratio \+ 0.4 \* token\_sort\_ratio \+ 0.2 \* WRatio.  
  * Applies a penalty (\*= 0.7) if one title starts with a keyword (e.g., "correction", "erratum", "reply", "retraction") while the other does not.  
* **Author Score:**  
  * Applies several heuristics for comparing normalized author lists from the article and the preprint candidate:  
    * A match between valid, normalized ORCIDs results in a similarity score of 1.0 for that author pair.  
    * For authors without an ORCID match, the strategy iteratively finds the most similar pair of authors between the two lists using fuzz.token\_sort\_ratio on pre-calculated name variations (e.g., "J Smith", "Smith J", "John Smith").  
    * For efficiency with large author lists, the strategy compares sorted strings of all family names using fuzz.token\_sort\_ratio.  
    * The final author score is based on the sum of matched pair scores, normalized by the total number of authors from both lists: (2.0 \* score\_sum) / total\_authors.  
* **Final Weighted Score:** Calculated as: (weight\_year \* year\_score \+ weight\_title \* title\_score \+ weight\_author \* author\_score) / (total\_weights). Default weights heavily favor the title (2.0), followed by authors (0.8), and year (0.4).

### **Match Selection**

1. Only candidates achieving a final weighted score greater than or equal to min\_score (default 0.85) are considered potential matches.  
2. Among these, only candidates whose scores are within max\_score\_diff (default 0.03) of the highest score are returned as the final match(es). This selects the best result(s) when multiple candidates have very similar high scores.

### Results

| Metric                    |     Value |  
|:--------------------------|----------:|  
| True Positives (TP)       | 1427      |  
| False Positives (FP)      |   17      |  
| False Negatives (FN)      |   74      |  
| Precision                 |    0.9882 |  
| Recall                    |    0.9457 |  
| F0.5 Score                |    0.9794 |
| F1 Score                  |    0.9665 |
| F1.5 Score                |    0.9584 |
