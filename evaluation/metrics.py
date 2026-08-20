"""Metrics calculations for evaluation."""

from typing import List, Tuple


def compute_metrics(pred_lines: List[str], must_lines: List[str]) -> Tuple[float, float, float, int, int, int]:
    pred_set = set(l.strip() for l in pred_lines if l.strip())
    must_set = set(l.strip() for l in must_lines if l.strip())
    if not pred_set and not must_set:
        return 1.0, 1.0, 1.0, 0, 0, 0
    tp = len(pred_set & must_set)
    fp = len(pred_set - must_set)
    fn = len(must_set - pred_set)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return precision, recall, f1, tp, fp, fn
