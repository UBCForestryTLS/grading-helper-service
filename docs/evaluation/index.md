# Evaluation

!!! info "Status: Planned"
    The evaluation pipeline is designed but not yet implemented. Initial work started on branch `akshat/evaluation` (PR #4) but has been deferred in favor of core feature development.

## Goal

Before the grading tool can be trusted in production, we need to prove that AI grades are close enough to human grades. The evaluation pipeline will compare AI-generated grades against TA grades on the same submissions and produce statistical measures of agreement.

## Planned Methodology

1. **Collect paired data** — For a set of student submissions, collect both the TA's grade and the AI's grade
2. **Compute agreement metrics** — Measure how closely the AI matches the TA using standard inter-rater reliability measures
3. **Iterate on prompts** — Adjust the grading prompt in `GradingService._build_prompt()` until agreement metrics meet thresholds

## Planned Metrics

| Metric | What it measures | Target |
|--------|-----------------|--------|
| **Mean Absolute Error (MAE)** | Average point difference between AI and TA grades | < 0.5 points |
| **Root Mean Squared Error (RMSE)** | Penalizes large disagreements more heavily | < 1.0 point |
| **Cohen's Kappa** | Agreement adjusted for chance (for pass/fail or letter grade buckets) | > 0.7 (substantial agreement) |
| **Pearson Correlation** | Linear relationship between AI and TA scores | > 0.85 |

## Current Limitations

- The grading pipeline currently supports `short_answer_question`, `fill_in_multiple_blanks_question`, and `essay_question` types from Canvas
- No evaluation data has been collected yet — this requires running the tool on real course quizzes alongside TA grading
- The Bedrock grading prompt is functional but has not been optimized through evaluation cycles

## What "Good Enough" Means

The tool is designed to assist grading, not replace it entirely. The instructor always has the ability to review and override AI grades before releasing them. "Good enough" means:

- AI grades are within half a point of TA grades on average
- Obvious errors (e.g., giving full marks to a blank answer) never happen
- Feedback is pedagogically useful and rubric-aligned
- The instructor can trust the AI's first pass and only needs to correct outliers
