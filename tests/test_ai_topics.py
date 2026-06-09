from graz_protocols.ai_topics import annotate_topic_headings
from graz_protocols.topics import base_business_number


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeHttpClient:
    def __init__(self, payload: dict | None = None):
        self.calls: list[dict] = []
        self.payload = payload or {
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

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(self.payload)


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

    annotated = annotate_topic_headings(candidates, provider="openai", api_key="test-key", http_client=client)

    assert annotated[0]["label"] == "Klimabeirat und Klimaschutzplan"
    assert annotated[0]["rule_label"] == "Geschäftsordnung Klimabeirats"
    assert annotated[0]["ai_reason"] == "Gemeinsamer Inhalt der beiden Überschriften"
    assert annotated[0]["ai_confidence"] == 0.82
    assert annotated[0]["label_source"] == "ki"
    assert client.calls[0]["headers"]["Authorization"] == "Bearer test-key"
    assert client.calls[0]["json"]["text"]["format"]["type"] == "json_schema"


def test_annotate_topic_headings_uses_ollama_by_default():
    client = FakeHttpClient(
        {
            "message": {
                "content": (
                    '```json\n{"label":"Klimabeirat und Klimaschutzplan",'
                    '"reason":"Gemeinsamer Inhalt",'
                    '"confidence":0.77}\n```'
                )
            }
        }
    )
    candidates = [
        {
            "label": "Geschäftsordnung Klimabeirats",
            "records": [
                {"meeting_date": "2025-11-13", "title": "Geschäftsordnung des Klimabeirats der Stadt Graz"},
            ],
        }
    ]

    annotated = annotate_topic_headings(
        candidates,
        model="qwen2.5:7b-instruct",
        base_url="http://localhost:11434",
        http_client=client,
    )

    assert annotated[0]["label"] == "Klimabeirat und Klimaschutzplan"
    assert annotated[0]["ai_confidence"] == 0.77
    assert client.calls[0]["url"] == "http://localhost:11434/api/chat"
    assert client.calls[0]["json"]["model"] == "qwen2.5:7b-instruct"
    assert client.calls[0]["json"]["format"] == "json"
    assert "Authorization" not in client.calls[0]


def test_base_business_number_groups_trailing_file_variants():
    assert base_business_number("A14-081274/2023/0382") == "A14-081274/2023"
    assert base_business_number("A 14-081274/2023/0428-4") == "A14-081274/2023"
    assert base_business_number("A 14-081274/2023/0439") == "A14-081274/2023"
