# Speaker Identification Sensitivity Analysis

**Generated from:** 301 recordings
**Labeled speakers:** 224
**Unique participants:** 41

---

## 1. Similarity Distributions

### Same Person (Cross-Recording)

| Metric | Value |
|--------|-------|
| Count | 2542 pairs |
| Mean | 0.598 |
| Std Dev | 0.098 |
| Min | 0.197 |
| Max | 1.000 |
| 5th percentile | 0.426 |
| 25th percentile | 0.538 |
| Median | 0.606 |
| 75th percentile | 0.664 |
| 95th percentile | 0.747 |

### Different People

| Metric | Value |
|--------|-------|
| Count | 190 pairs |
| Mean | 0.084 |
| Std Dev | 0.103 |
| Min | -0.333 |
| Max | 0.466 |
| 5th percentile | -0.061 |
| 25th percentile | 0.027 |
| Median | 0.072 |
| 75th percentile | 0.129 |
| 95th percentile | 0.271 |

**Separation:** 0.514 (same - different means)

---

## 2. Threshold Analysis

| Threshold | Precision | Recall | F1 | Accuracy | TP | FP | TN | FN |
|-----------|-----------|--------|-------|----------|-----|-----|-----|-----|
| 0.50 ** | 1.000 | 0.847 | 0.917 | 0.858 | 2153 | 0 | 190 | 389 |
| 0.55 | 1.000 | 0.712 | 0.832 | 0.732 | 1811 | 0 | 190 | 731 |
| 0.60 | 1.000 | 0.524 | 0.688 | 0.557 | 1332 | 0 | 190 | 1210 |
| 0.65 | 1.000 | 0.311 | 0.474 | 0.359 | 790 | 0 | 190 | 1752 |
| 0.70 | 1.000 | 0.137 | 0.240 | 0.197 | 347 | 0 | 190 | 2195 |
| 0.72 | 1.000 | 0.092 | 0.168 | 0.155 | 233 | 0 | 190 | 2309 |
| 0.74 | 1.000 | 0.062 | 0.117 | 0.127 | 158 | 0 | 190 | 2384 |
| 0.76 | 1.000 | 0.032 | 0.062 | 0.100 | 82 | 0 | 190 | 2460 |
| 0.78 | 1.000 | 0.015 | 0.029 | 0.083 | 38 | 0 | 190 | 2504 |
| 0.80 | 1.000 | 0.007 | 0.014 | 0.076 | 18 | 0 | 190 | 2524 |
| 0.82 | 1.000 | 0.004 | 0.008 | 0.073 | 10 | 0 | 190 | 2532 |
| 0.85 | 1.000 | 0.001 | 0.002 | 0.071 | 3 | 0 | 190 | 2539 |
| 0.88 | 1.000 | 0.001 | 0.002 | 0.071 | 3 | 0 | 190 | 2539 |
| 0.90 | 1.000 | 0.001 | 0.002 | 0.071 | 3 | 0 | 190 | 2539 |

**Best F1 Score:** 0.50 (F1 = 0.917)
**Best for High Precision (≥95%):** 0.50 (P=1.000, R=0.847)

### Recommendations

⚠️ **Overlap zone:** 0.271 - 0.426
   Similarities in this range are ambiguous.

- **Auto-assign threshold:** 0.50 (high confidence)
- **Suggest threshold:** 0.50 (balanced)
- **Reject threshold:** 0.27 (below this, definitely different)

---

## 3. Centroid vs Raw Embedding Comparison

Comparing 2542 same-person pairs across recordings:

| Method | Mean Similarity | Std Dev | Min | Max |
|--------|-----------------|---------|-----|-----|
| Centroid | 0.598 | 0.098 | 0.197 | 1.000 |
| Raw (mean of pairs) | 0.528 | 0.073 | 0.250 | 0.772 |
| Raw (max of pairs) | 0.696 | 0.065 | 0.444 | 1.000 |

**Centroid is better** by 0.070 on average

---

## 4. Transitive Chain Risk Analysis

Testing at threshold 0.75:

- Edges above threshold: 113
- A→B→C chains checked: 397
- **Violations found: 0**
- Violation rate: 0.00%

✅ **No chain violations found** at this threshold.

---

## 5. Per-Participant Consistency

How consistent are embeddings for each known participant?

| Participant | Recordings | Mean Sim | Min Sim | Max Sim | Std |
|-------------|------------|----------|---------|---------|-----|
| Chris | 68 | 0.591 | 0.197 | 1.000 | 0.095 |
| Rob | 11 | 0.732 | 0.612 | 0.840 | 0.059 |
| Courtney | 11 | 0.666 | 0.477 | 0.772 | 0.064 |
| Kristy | 8 | 0.684 | 0.523 | 1.000 | 0.088 |
| Erin | 8 | 0.637 | 0.410 | 1.000 | 0.124 |
| Carmen | 8 | 0.570 | 0.418 | 0.727 | 0.078 |
| Kat | 6 | 0.528 | 0.280 | 0.774 | 0.143 |
| Emerson | 5 | 0.577 | 0.488 | 0.657 | 0.063 |
| Jonathan | 5 | 0.714 | 0.568 | 0.834 | 0.090 |
| Jenna | 5 | 0.620 | 0.490 | 0.751 | 0.082 |
| Nicole | 4 | 0.578 | 0.505 | 0.674 | 0.063 |
| Alberto | 4 | 0.714 | 0.686 | 0.760 | 0.029 |
| Rudy | 4 | 0.616 | 0.458 | 0.746 | 0.084 |
| Marilee | 2 | 0.634 | 0.634 | 0.634 | 0.000 |
| Madeline | 2 | 0.789 | 0.789 | 0.789 | 0.000 |

⚠️ **Participants with low minimum similarity (<0.70):**
- Chris: min=0.197
- Rob: min=0.612
- Courtney: min=0.477
- Kristy: min=0.523
- Erin: min=0.410
- Carmen: min=0.418
- Kat: min=0.280
- Emerson: min=0.488
- Jonathan: min=0.568
- Jenna: min=0.490
- Nicole: min=0.505
- Alberto: min=0.686
- Rudy: min=0.458
- Marilee: min=0.634
- Peggy: min=0.625
- Tom: min=0.686
- Jason: min=0.673
- Bryan: min=0.670

---

## 6. Same-Recording Anomalies (Potential Diarization Errors)

Speakers within the same recording with similarity ≥ 0.75:

No same-recording anomalies found.

---

## Summary & Recommendations

### Threshold Recommendations

1. **High Confidence (auto-assign):** ≥ 0.50
2. **Medium Confidence (suggest):** 0.50 - 0.50
3. **Reject (different person):** < 0.27

### Approach Recommendations

✅ Use **centroid-based matching** (better separation)
✅ Transitive chains are relatively safe (<5% violations)
