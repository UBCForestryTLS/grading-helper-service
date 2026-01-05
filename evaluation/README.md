# LLM Grading Evaluation

This evaluation assesses whether Large Language Models can accurately approximate instructor grading on short-answer questions.

## Purpose

Before using LLMs in the grading helper service, we need evidence that they can reliably grade student work. This evaluation provides that evidence by comparing LLM grades to human instructor grades on real student data.

## Methodology

We followed the approach from **Impey et al. (2025)** - "Using Large Language Models for Automated Grading of Student Writing about Science" - which evaluated LLM grading on university astronomy courses.

### Data

- **Course**: CONS 127 (Conservation Science)
- **Offerings**: 6 terms (2021W2 through 2024S1)
- **Questions**: 81 short-answer questions
- **Submissions**: 3,549 student responses with instructor grades

### Prompt Conditions

We tested three different prompting strategies:

| Condition | Description | What the LLM receives |
|-----------|-------------|----------------------|
| **P1: Answer Only** | Simple prompt with just the acceptable answers | Question + acceptable answers + student response |
| **P2: Answer + Rubric** | Adds explicit grading criteria | Above + rubric with full/partial/zero credit criteria |
| **P3: LLM-Generated Rubric** | LLM creates its own rubric first | LLM generates rubric, then uses it to grade |

### Models Tested

- **Llama 3 70B Instruct** (via AWS Bedrock)
- Additional models (Mistral, Claude) available but require access approval

### Statistical Analysis

Following the paper's methodology:
- **Shapiro-Wilk test**: Check if grade distributions are normal
- **Friedman test**: Compare the three prompt conditions
- **Correlation (Pearson/Spearman)**: Measure agreement with instructor
- **RMS Difference**: Quantify average error magnitude
- **Bootstrap confidence intervals**: Estimate uncertainty

---

## Results Summary

### Performance by Prompt Condition

| Metric | P1 (Answer Only) | P2 (Answer+Rubric) | P3 (LLM Rubric) |
|--------|:----------------:|:------------------:|:---------------:|
| **Exact Match (±1%)** | **76.5%** ✓ | 75.0% | 75.7% |
| **RMS Difference** | **32.0%** ✓ | 34.4% | 38.7% |
| **Correlation (r)** | **0.784** ✓ | 0.748 | 0.699 |
| **Bias (LLM - Instructor)** | -3.4% | +3.2% | -8.7% |

### Key Findings

1. **Best performer**: Prompt 1 (Answer Only) - surprisingly, the simplest approach worked best for this dataset

2. **Accuracy**: 76.5% of LLM grades exactly match instructor grades within ±1%

3. **Correlation**: Strong positive correlation (r = 0.78) indicates the LLM generally agrees with instructor patterns

4. **Bias**: LLM tends to be slightly stricter than the instructor (-3.4% on average)

5. **Error breakdown**:
   - 5.4% false negatives (LLM gave 0% when instructor gave 100%)
   - 4.1% false positives (LLM gave 100% when instructor gave 0%)

### Comparison to Reference Paper

| Aspect | Impey et al. (2025) | Our Evaluation |
|--------|---------------------|----------------|
| Agreement Rate | ~92% | 76.5% |
| Model | GPT-4 / Claude | Llama 3 70B |
| Question Type | Essay responses | Short-answer |
| LLM Bias | Lenient (grades higher) | Strict (grades lower) |

The lower agreement rate is likely due to:
- Using Llama 3 instead of GPT-4/Claude
- Different question complexity
- Our data has mostly binary grades (0% or 100%)

---

## How to Use the Notebook

### Prerequisites

1. **AWS Bedrock access** with credentials configured
2. **Python environment** with dependencies installed:
   ```bash
   uv sync --group evaluation
   ```

### Setup

1. Create a `.env` file in the `evaluation/` directory:
   ```
   AWS_ACCESS_KEY_ID=your-key
   AWS_SECRET_ACCESS_KEY=your-secret
   # Or if using Bedrock API key:
   AWS_BEARER_TOKEN_BEDROCK=your-token
   ```

2. Place your data in `evaluation/data/` following this structure:
   ```
   data/
   ├── CONS 127/
   │   ├── 2021W2/
   │   │   └── questions_submissions-cid_XXXXX.json
   │   ├── 2022W1/
   │   └── ...
   ```

### Running the Evaluation

1. Start JupyterLab:
   ```bash
   cd evaluation
   uv run jupyter lab
   ```

2. Open `llm_grading_evaluation.ipynb`

3. Run cells in order:
   - **Cells 1-5**: Setup, configuration, data loading
   - **Cells 6-9**: Data exploration and visualization
   - **Cells 10-13**: Prompt templates and LLM functions
   - **Cells 14-16**: Pilot test (quick validation)
   - **Cells 17-19**: Full evaluation (takes ~20 min with 4 workers)
   - **Cells 20-27**: Statistical analysis and visualization

### Speed Optimization

The full evaluation can be slow. To speed it up:

```python
# In cell 18, reduce sample size:
SUBMISSIONS_PER_QUESTION = 5  # Default is 10

# In cell 19, use fewer models:
MODELS = {"llama3-70b": "meta.llama3-70b-instruct-v1:0"}

# Increase parallel workers (may hit rate limits):
results_df = run_full_evaluation(..., max_workers=8)
```

---

## Notebook Structure

| Section | Cells | Description |
|---------|-------|-------------|
| **1. Setup** | 1-3 | Imports, AWS config, model definitions |
| **2. Data Loading** | 4-5 | Load JSON files into DataFrame |
| **3. Exploration** | 6-9 | Summary stats, grade distribution, sample questions |
| **4. Prompts** | 10-11 | Define the 3 prompt templates |
| **5. LLM Functions** | 12-13 | Bedrock API calls, response parsing |
| **6. Pilot Test** | 14-16 | Quick test on 5 submissions |
| **7. Full Evaluation** | 17-19 | Run all models × conditions × samples |
| **8. Statistics** | 20-23 | Normality, Friedman test, ICC, bootstrap CI |
| **9. Visualization** | 24-25 | Scatter plots, histograms, heatmaps |
| **10. Summary** | 26-29 | Results tables, export to CSV |

---

## Output Files

After running the evaluation, results are saved to `evaluation/results/`:

| File | Description |
|------|-------------|
| `grading_results.csv` | All individual grading results |
| `summary_statistics.csv` | Aggregated metrics by prompt condition |
| `figures/evaluation_summary.png` | Visual summary plots |
| `figures/grade_distributions.png` | Grade histograms |
| `figures/scatter_plots.png` | Instructor vs LLM scatter |

---

## Recommendations

Based on the evaluation results:

### ✅ Safe to Use
- Initial screening of submissions
- Flagging obviously correct/incorrect answers
- Reducing grading workload by ~75%

### ⚠️ Requires Human Review
- Partial credit situations
- Questions where LLM has low match rate
- Any grade the instructor hasn't seen yet

### 🔄 Future Improvements
1. Test Claude models (once Bedrock access approved)
2. Fine-tune prompts for specific question types
3. Add confidence scores to flag uncertain grades
4. Test on NRES 241 course data

---

## References

- Impey, C., et al. (2025). "Using Large Language Models for Automated Grading of Student Writing about Science." *Astronomy Education Journal*.
