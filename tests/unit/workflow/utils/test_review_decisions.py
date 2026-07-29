from forge.workflow.utils.review_decisions import merge_review_decisions


def test_merge_keeps_latest_decision_per_thread() -> None:
    previous = [
        {"thread_id": "thread-a", "disposition": "reply"},
        {"thread_id": "thread-b", "disposition": "accept"},
    ]
    current = [{"thread_id": "thread-a", "disposition": "accept"}]

    assert merge_review_decisions(previous, current) == [
        {"thread_id": "thread-a", "disposition": "accept"},
        {"thread_id": "thread-b", "disposition": "accept"},
    ]


def test_merge_ignores_items_without_thread_identity() -> None:
    assert merge_review_decisions([{"text": "legacy"}], [{"disposition": "accept"}]) == []
