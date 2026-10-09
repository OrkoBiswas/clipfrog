import pytest
from clipforge_worker.highlights.heuristic_ranker import DEFAULT_WEIGHTS
from clipforge_worker.highlights.learning import Example, learn_weights


def example(good, difference=0.7, index=0):
    features = dict.fromkeys(DEFAULT_WEIGHTS, 0.5)
    features["insight"] = (0.5 + difference / 2 if good else 0.5 - difference / 2) - index * 0.01
    features["visual"] = (0.5 - difference / 2 if good else 0.5 + difference / 2) + index * 0.01
    return Example(features, good)


def test_learner_waits_for_both_classes_and_never_labels_its_own_predictions():
    report = learn_weights([example(True) for _ in range(20)])
    assert report["status"] == "collecting_feedback"
    assert report["weights"] == DEFAULT_WEIGHTS


def test_explicit_preferences_improve_held_out_check_with_bounded_weights():
    examples = [example(good, index=i) for good in [True, False] for i in range(5)]
    report = learn_weights(examples)
    assert report["status"] == "personalized"
    assert report["validation"]["learned_loss"] < report["validation"]["baseline_loss"]
    assert report["weights"]["insight"] > DEFAULT_WEIGHTS["insight"]
    assert report["weights"]["visual"] < DEFAULT_WEIGHTS["visual"]
    assert sum(report["weights"].values()) == pytest.approx(100)
    for key, weight in report["weights"].items():
        assert DEFAULT_WEIGHTS[key] * 0.75 <= weight <= DEFAULT_WEIGHTS[key] * 1.25
    assert learn_weights(examples) == report


def test_indistinguishable_ratings_do_not_activate_training():
    examples = [
        Example(dict.fromkeys(DEFAULT_WEIGHTS, 0.5), good)
        for good in [True, False]
        for _ in range(4)
    ]
    report = learn_weights(examples)
    assert report["status"] == "needs_more_variety"
    assert report["weights"] == DEFAULT_WEIGHTS


def test_invalid_and_nonfinite_training_samples_are_excluded():
    report = learn_weights(
        [Example({"hook": float("nan")}, True), Example(dict.fromkeys(DEFAULT_WEIGHTS, 4), False)]
    )
    assert report["good_ratings"] == 0
    assert report["poor_ratings"] == 0
