from graz_protocols.ai_summaries import annotate_record_summaries


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
                "message": {
                    "content": (
                        '{"summary":"Das Stück behandelt eine Verkehrsmaßnahme und das Ergebnis der Abstimmung.",'
                        '"easy_language":"Es geht um eine Straße. Die Stadt entscheidet darüber. Das Ergebnis steht dabei."}'
                    )
                }
            }
        )


def test_annotate_record_summaries_uses_local_ollama():
    client = FakeHttpClient()
    records = [
        {
            "meeting_date": "2025-01-16",
            "title": "Unfallhäufungsstelle Marburger Straße",
            "result_text": "Verfahren: zugewiesen",
            "locations": ["Marburger Straße"],
        }
    ]

    enriched = annotate_record_summaries(
        records,
        model="qwen2.5:7b-instruct",
        base_url="http://localhost:11434",
        http_client=client,
    )

    assert enriched[0]["ai_summary"].startswith("Das Stück behandelt")
    assert enriched[0]["ai_easy_language"].startswith("Es geht um")
    assert client.calls[0]["url"] == "http://localhost:11434/api/chat"
    assert client.calls[0]["json"]["model"] == "qwen2.5:7b-instruct"
    assert client.calls[0]["json"]["format"] == "json"
