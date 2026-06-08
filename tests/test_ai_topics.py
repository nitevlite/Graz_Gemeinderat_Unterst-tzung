from graz_protocols.ai_topics import annotate_topic_headings


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeHttpClient:
    def __init__(self):
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(
            {
                "output": [
                    {
                        "content": [
                            {
                                "text": (
                                    '{"label":"Klimabeirat und Klimaschutzplan",'
                                    '"reason":"Gemeinsamer Inhalt der beiden Überschriften",'
                                    '"confidence":0.82}'
                                )
                            }
                        ]
                    }
                ]
            }
        )


def test_annotate_topic_headings_uses_structured_response_payload():
    client = FakeHttpClient()
    candidates = [
        {
            "label": "Geschäftsordnung Klimabeirats",
            "business_number": "A23-032670/2020",
            "reason": "gleiche Geschäftszahl-Basis",
            "dates": ["2025-11-13", "2025-12-11"],
            "records": [
                {"meeting_date": "2025-11-13", "title": "Geschäftsordnung des Klimabeirats der Stadt Graz"},
                {"meeting_date": "2025-12-11", "title": "Klimaschutzplan Graz - Fortschrittsbericht"},
            ],
        }
    ]

    annotated = annotate_topic_headings(candidates, api_key="test-key", http_client=client)

    assert annotated[0]["label"] == "Klimabeirat und Klimaschutzplan"
    assert annotated[0]["rule_label"] == "Geschäftsordnung Klimabeirats"
    assert annotated[0]["ai_reason"] == "Gemeinsamer Inhalt der beiden Überschriften"
    assert annotated[0]["ai_confidence"] == 0.82
    assert annotated[0]["label_source"] == "ki"
    assert client.calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert client.calls[0]["json"]["text"]["format"]["type"] == "json_schema"
