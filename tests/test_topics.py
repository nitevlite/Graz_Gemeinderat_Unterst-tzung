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

    business_candidate = next(candidate for candidate in candidates if candidate["business_number"] == "A10-123")
    assert business_candidate["label"] == "Projekt Reininghaus"
    assert any(candidate["label"] == "Projekt Reininghaus" for candidate in candidates)
    assert all("confidence" in candidate for candidate in candidates)


def test_topic_label_avoids_business_codes_as_heading():
    records = [
        {
            "record_id": "a",
            "meeting_date": "2025-11-13",
            "record_type": "agenda_item",
            "agenda_item_no": 4,
            "business_numbers": ["A23-032670/2020/1"],
            "title": "A10/BD-085394/2019-0099, Geschäftsordnung des Klimabeirats der Stadt Graz Adaptierung der bestehenden Geschäftsordnung",
            "result_source": "digra",
        },
        {
            "record_id": "b",
            "meeting_date": "2025-12-11",
            "record_type": "agenda_item",
            "agenda_item_no": 12,
            "business_numbers": ["A23-032670/2020/2"],
            "title": "A10/BD-085394/2019-0097; Klimaschutzplan Graz - 3. Fortschrittsbericht und weitere Vorgangsweise",
            "result_source": "protokoll",
        },
    ]

    candidates = build_topic_candidates(records)

    business_candidate = next(candidate for candidate in candidates if candidate["business_number"] == "A23-032670/2020")
    assert business_candidate["label"] == "Geschäftsordnung Klimabeirats"
    assert "BD-085394" not in business_candidate["label"]
