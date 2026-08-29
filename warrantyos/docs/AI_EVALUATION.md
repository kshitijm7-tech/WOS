# AI Evaluation Harness — WarrantyOS Part 2.6

## Overview

The Part 2.6 evaluation framework provides continuous measurement of AI recommendation quality, human-AI agreement, confidence calibration, and retrieval precision.

## Evaluation Metrics

### 1. Human-AI Agreement & Override Breakdown
- **Observed Agreement**: Proportion of reviewed claims where AI recommendation matches human decision.
- **Approval & Rejection Rates**: Distribution of human approval vs rejection outcomes.
- **Override Rate by Recommendation**: Override frequency broken down by recommendation type (`REPAIR`, `REPLACE`, `DENY`, `MORE_INFORMATION_REQUIRED`, `HUMAN_REVIEW`).
- **Agreement by Confidence Band**: Agreement rates across `HIGH` (≥0.80), `MEDIUM` (0.50–0.79), and `LOW` (<0.50) confidence bands.

### 2. Confidence Calibration
- **Brier Score**: Mean squared error between AI predicted confidence and binary human agreement outcome.
- **Calibration Error (ECE)**: Expected calibration error measuring alignment between confidence bins and observed accuracy.
- **Status Reporting**: Set to `SUFFICIENT_DATA` when sample size ≥ 5, otherwise explicitly reported as `INSUFFICIENT_DATA`.

### 3. Recommendation Classification Metrics
- Precision, Recall, F1-score, and Confusion Matrix per recommendation class.
- Reported as `insufficient_samples` when class sample count < 2.

### 4. Historical Retrieval Quality
- Evaluates `Precision@K`, `Recall@K`, `Hit@K`, `MRR`, and `Average Similarity` for K ∈ [1, 3, 5].
- Explicitly reports `status: "insufficient_ground_truth"` when labeled cases count < 3.

## Golden Benchmark Dataset

Deterministic fixtures covering Scenarios A through H:
- **Scenario A**: Clean valid warranty claim.
- **Scenario B**: Missing proof of purchase invoice.
- **Scenario C**: Expired warranty period.
- **Scenario D**: Serial number mismatch between invoice OCR and registered product.
- **Scenario E**: Customer with multiple claims in 90 days.
- **Scenario F**: High confidence clean history.
- **Scenario G**: Physical / accidental damage policy exclusion conflict.
- **Scenario H**: Ineligible warranty with conflicting AI recommendation.
