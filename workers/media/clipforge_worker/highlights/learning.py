"""Small, private supervised preference learner; no self-labels or network calls."""

import math
from collections.abc import Mapping
from dataclasses import dataclass

from clipforge_worker.highlights.heuristic_ranker import DEFAULT_WEIGHTS, ENGINE_VERSION


@dataclass(frozen=True)
class Example:
    features: dict[str, float]
    good: bool


def valid_features(features: dict) -> bool:
    return set(features) == set(DEFAULT_WEIGHTS) and all(
        isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 1
        for value in features.values()
    )


def _fit(examples: list[Example], baseline: dict[str, float]) -> dict[str, float]:
    good = [e for e in examples if e.good]
    poor = [e for e in examples if not e.good]
    if not good or not poor:
        return dict(baseline)
    factors = {}
    for key in baseline:
        difference = sum(e.features[key] for e in good) / len(good) - sum(
            e.features[key] for e in poor
        ) / len(poor)
        factors[key] = baseline[key] * (1 + 0.25 * math.tanh(difference * 4))
    # A scalar multiplier projected onto a box keeps total=100 and every
    # component within +/-25% of the configured editorial prior.
    low, high = 0.0, 4.0
    for _ in range(60):
        scale = (low + high) / 2
        total = sum(
            min(baseline[k] * 1.25, max(baseline[k] * 0.75, factors[k] * scale)) for k in baseline
        )
        if total < 100:
            low = scale
        else:
            high = scale
    return {
        k: min(baseline[k] * 1.25, max(baseline[k] * 0.75, factors[k] * (low + high) / 2))
        for k in baseline
    }


def _score(features: dict[str, float], weights: dict[str, float]) -> float:
    return sum(features[k] * weights[k] for k in weights) / 100


def learn_weights(examples: list[Example], baseline: Mapping[str, float] | None = None) -> dict:
    baseline = dict(baseline or DEFAULT_WEIGHTS)
    examples = [e for e in examples if valid_features(e.features)][-400:]
    good, poor = sum(e.good for e in examples), sum(not e.good for e in examples)
    report = {
        "engine_version": ENGINE_VERSION,
        "mode": "local",
        "status": "collecting_feedback",
        "good_ratings": good,
        "poor_ratings": poor,
        "weights": baseline,
        "message": "Rate at least 3 good and 3 poor moments to evaluate your preferences.",
    }
    if good < 3 or poor < 3:
        return report
    # Each rating is held out while estimating weights and the opposing class.
    # Activation requires lower held-out pairwise loss and no accuracy decline.
    losses = [0.0, 0.0]
    correct = [0.0, 0.0]
    for index, example in enumerate(examples):
        training = examples[:index] + examples[index + 1 :]
        opposite = [e for e in training if e.good != example.good]
        anchor = {k: sum(e.features[k] for e in opposite) / len(opposite) for k in baseline}
        for mode, weights in enumerate((baseline, _fit(training, baseline))):
            margin = (_score(example.features, weights) - _score(anchor, weights)) * (
                1 if example.good else -1
            )
            losses[mode] += math.log1p(math.exp(-4 * margin)) / len(examples)
            correct[mode] += (1 if margin > 1e-9 else 0.5 if abs(margin) <= 1e-9 else 0) / len(
                examples
            )
    report["validation"] = {
        "method": "leave_one_rating_out",
        "baseline_loss": round(losses[0], 6),
        "learned_loss": round(losses[1], 6),
        "baseline_accuracy": round(correct[0], 4),
        "learned_accuracy": round(correct[1], 4),
    }
    if losses[1] < losses[0] - 0.003 and correct[1] >= correct[0] - 1e-9:
        report.update(
            status="personalized",
            weights=_fit(examples, baseline),
            message="Your ratings improved the preference check. Future highlight searches use your learned weights.",
        )
    else:
        report.update(
            status="needs_more_variety",
            message="Your ratings are saved. More varied examples are needed before changing the ranking.",
        )
    return report
