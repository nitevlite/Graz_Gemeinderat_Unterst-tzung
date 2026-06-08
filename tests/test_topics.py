from graz_protocols.topics import build_topic_candidates


def test_builds_topic_candidates_from_repeated_keywords_and_business_numbers():
    records = [
        {
            "record_id": "a",
            "meeting_date": "2025-01-16",
            "record_type": "agenda_item",
            "agenda_item_no": 1,
            "business_numbers": ["A10-123/1"],
            "title": "Projekt Reininghaus Verkehrsanbindung",
            "result_source": "digra",
        },
        {
            "record_id": "b",
            "meeting_date": "2025-02-13",
            "record_type": "agenda_item",
            "agenda_item_no": 2,
            "business_numbers": ["A10-123/2"],
            "title": "Projekt Reininghaus Budgetanpassung",
            "result_source": "protokoll",
        },
    ]

    candidates = build_topic_candidates(records)

    assert any(candidate["label"] == "A10-123" for candidate in candidates)
    assert any(candidate["label"] == "reininghaus" for candidate in candidates)
    assert all("confidence" in candidate for candidate in candidates)
