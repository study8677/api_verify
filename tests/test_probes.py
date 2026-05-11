from api_verify.probes import build_default_probes


def test_default_probe_suite_has_required_categories():
    probes = build_default_probes("gpt-4.1", sample_count=2)
    categories = {probe.category for probe in probes}

    assert categories == {
        "metadata",
        "parameter_fidelity",
        "capability",
        "error_semantics",
        "statistical_behavior",
    }
    assert sum(probe.repeats for probe in probes if probe.category == "statistical_behavior") == 2
