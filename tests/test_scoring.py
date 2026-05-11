from api_verify.scoring import score_records


def test_score_error_semantics_accepting_invalid_parameter_is_suspicious():
    report = score_records(
        [
            {
                "run_id": "r1",
                "probe_id": "error.invalid_parameter",
                "probe_category": "error_semantics",
                "status": 200,
                "response_json": {"choices": [{"message": {"content": "ok"}}]},
                "response_text": "{}",
                "dry_run": False,
            }
        ]
    )

    assert report["verdict"] == "强可疑"
    assert report["evidence"][0]["score"] == 25


def test_metadata_scoring_warns_that_fields_are_forgeable():
    report = score_records(
        [
            {
                "run_id": "r2",
                "probe_id": "metadata.basic_chat",
                "probe_category": "metadata",
                "status": 200,
                "request": {"model": "gpt-4.1"},
                "response_json": {
                    "model": "gpt-4.1",
                    "usage": {"prompt_tokens": 10, "completion_tokens": 3},
                    "choices": [{"message": {"content": "API_VERIFY_METADATA_OK"}}],
                },
                "dry_run": False,
            }
        ]
    )

    assert "可伪造" in report["field_forgery_warning"]
    assert report["verdict"] == "通过"


def test_statistical_behavior_accepts_expected_answer_17():
    report = score_records(
        [
            {
                "run_id": "r3",
                "probe_id": "statistical.simple_reasoning",
                "probe_category": "statistical_behavior",
                "status": 200,
                "response_json": {"choices": [{"message": {"content": "17"}}]},
                "usage": {"prompt_tokens": 30, "completion_tokens": 1},
                "latency_ms": 1200,
                "dry_run": False,
            }
        ]
    )

    assert report["verdict"] == "通过"
    assert report["evidence"][0]["score"] >= 75
    assert "answer matches deterministic expected result" in report["evidence"][0]["rationale"]
    assert "answer differs from expected result" not in report["evidence"][0]["rationale"]
    assert report["evidence"][0]["artifact_ref"] == "runs.jsonl#r3"
