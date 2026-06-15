from __future__ import annotations

from dataclasses import asdict, dataclass
from html.parser import HTMLParser
import re
from urllib.parse import urljoin
from urllib.request import Request, urlopen


GRAZ_OFFICES_URL = "https://www.graz.at/cms/beitrag/10019383/7743948/Aemter_und_Politik.html"
GRAZ_COUNCIL_MEMBERS_URL = "https://www.graz.at/cms/beitrag/10379731/7768104/Gemeinderat_Mitglieder.html"
GRAZ_COUNCIL_SEATS_URL = "https://www.graz.at/cms/ziel/7769043/DE/"
GRAZ_CITY_GOVERNMENT_URL = "https://www.graz.at/cms/ziel/7765844/DE/"
GRAZ_PHONEBOOK_URL = "https://www.graz.at/cms/ziel/7536192/"
GRAZ_APPOINTMENTS_URL = "https://www.graz.at/termine"
GRAZ_CONTACT_FORM_URL = "https://www.graz.at/cms/beitrag/10303721/8425359/"
GRAZ_DIGITAL_CITY_URL = "https://www.digitalestadt.graz.at/"
GRAZ_WEBSITE_LICENSE = "öffentliche Webseite, keine OGD-Lizenz gefunden"
GRAZ_WEBSITE_REUSE = (
    "Im Open-Source-Projekt werden nur kurze, faktische Servicehinweise und Links geführt. "
    "Aktuelle Öffnungszeiten, Zuständigkeiten und Formulare bleiben auf den offiziellen Seiten."
)
GRAZ_HTTP_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class CivicService:
    name: str
    category: str
    address: str
    lat: float
    lon: float
    description: str
    services: list[str]
    phone: str = ""
    email: str = ""
    website: str = ""
    appointments_url: str = GRAZ_APPOINTMENTS_URL
    source: str = "Stadt Graz"
    source_url: str = GRAZ_OFFICES_URL
    license: str = GRAZ_WEBSITE_LICENSE
    reuse: str = GRAZ_WEBSITE_REUSE


@dataclass(frozen=True)
class CouncilGroup:
    name: str
    short_name: str
    seats: int
    color: str
    text_color: str
    members: list[dict[str, str]]
    note: str = ""


@dataclass(frozen=True)
class CitySenateGroup:
    name: str
    short_name: str
    seats: int
    color: str
    text_color: str
    members: list[dict[str, str]]


def load_civic_services() -> tuple[list[dict], dict]:
    services = [asdict(service) for service in CIVIC_SERVICES]
    return services, civic_service_summary(records=len(services))


def load_civic_council(fetch_live: bool = False) -> dict:
    live_groups = load_live_council_groups() if fetch_live else []
    live_senate_groups = load_live_city_senate_groups() if fetch_live else []
    council_groups = live_groups
    if not live_groups:
        council_groups = [asdict(group) for group in COUNCIL_GROUPS]
    senate_groups = live_senate_groups
    if not live_senate_groups:
        senate_groups = [asdict(group) for group in CITY_SENATE_GROUPS]
    return {
        "title": "Grazer Gemeinderat",
        "period": "aktuelle Zusammensetzung laut graz.at" if live_groups else "lokaler Fallback nach graz.at",
        "total_seats": sum(group["seats"] for group in council_groups),
        "majority_seats": (sum(group["seats"] for group in council_groups) // 2) + 1,
        "groups": council_groups,
        "city_senate": {
            "title": "Stadtregierung",
            "total_seats": sum(group["seats"] for group in senate_groups),
            "groups": senate_groups,
        },
        "sources": {
            "members_url": GRAZ_COUNCIL_MEMBERS_URL,
            "seats_url": GRAZ_COUNCIL_SEATS_URL,
            "city_government_url": GRAZ_CITY_GOVERNMENT_URL,
            "attribution": "Stadt Graz",
            "license": GRAZ_WEBSITE_LICENSE,
            "reuse": GRAZ_WEBSITE_REUSE,
        },
    }


def load_live_council_groups() -> list[dict]:
    try:
        request = Request(GRAZ_COUNCIL_MEMBERS_URL, headers={"User-Agent": "graz-protocols-viewer/1.0"})
        with urlopen(request, timeout=GRAZ_HTTP_TIMEOUT_SECONDS) as response:
            html_text = response.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return parse_council_member_links(html_text, GRAZ_COUNCIL_MEMBERS_URL)


def load_live_city_senate_groups() -> list[dict]:
    try:
        request = Request(GRAZ_CITY_GOVERNMENT_URL, headers={"User-Agent": "graz-protocols-viewer/1.0"})
        with urlopen(request, timeout=GRAZ_HTTP_TIMEOUT_SECONDS) as response:
            html_text = response.read().decode("utf-8", errors="replace")
    except OSError:
        return []
    return parse_city_senate_member_links(html_text, GRAZ_CITY_GOVERNMENT_URL)


def parse_council_member_links(html_text: str, base_url: str = GRAZ_COUNCIL_MEMBERS_URL) -> list[dict]:
    parser = CouncilMemberLinkParser(base_url)
    parser.feed(html_text)
    grouped: dict[str, list[dict[str, str]]] = {}
    for link in parser.links:
        party = council_party_from_label(link["label"])
        name = council_member_name_from_label(link["label"])
        if not party or not name:
            continue
        grouped.setdefault(party, [])
        if all(existing["name"] != name for existing in grouped[party]):
            grouped[party].append({"name": name, "url": link["url"]})
    groups: list[dict] = []
    for party, members in grouped.items():
        meta = COUNCIL_GROUP_META.get(party, fallback_council_group_meta(party))
        groups.append(
            {
                "name": meta["name"],
                "short_name": meta["short_name"],
                "seats": len(members),
                "color": meta["color"],
                "text_color": meta["text_color"],
                "members": members,
                "note": meta.get("note", ""),
            }
        )
    return sorted(groups, key=lambda group: (-group["seats"], COUNCIL_GROUP_ORDER.get(group["short_name"], 99), group["short_name"]))


def parse_city_senate_member_links(html_text: str, base_url: str = GRAZ_CITY_GOVERNMENT_URL) -> list[dict]:
    parser = CouncilMemberLinkParser(base_url)
    parser.feed(html_text)
    grouped: dict[str, list[dict[str, str]]] = {}
    for link in parser.links:
        label = link["label"]
        if not city_senate_label_has_role(label):
            continue
        party = council_party_from_label(label)
        name = city_senate_member_name_from_label(label)
        if not party or not name:
            continue
        grouped.setdefault(party, [])
        if all(existing["name"] != name for existing in grouped[party]):
            grouped[party].append({"name": name, "url": link["url"]})
    groups: list[dict] = []
    for party, members in grouped.items():
        meta = COUNCIL_GROUP_META.get(party, fallback_council_group_meta(party))
        groups.append(
            {
                "name": meta["name"],
                "short_name": meta["short_name"],
                "seats": len(members),
                "color": meta["color"],
                "text_color": meta["text_color"],
                "members": members,
            }
        )
    return sorted(groups, key=lambda group: (CITY_SENATE_GROUP_ORDER.get(group["short_name"], 99), group["short_name"]))


class CouncilMemberLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[dict[str, str]] = []
        self._href = ""
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href") or ""
        if not href:
            return
        self._href = urljoin(self.base_url, href)
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        label = re.sub(r"\s+", " ", "".join(self._parts)).strip()
        if label and "(" in label and ")" in label:
            self.links.append({"label": label, "url": self._href})
        self._href = ""
        self._parts = []


def council_party_from_label(label: str) -> str:
    full_text = label.casefold()
    party_text = " ".join(re.findall(r"\(([^)]*)\)", label)).casefold()
    if "kpö" in party_text or "kpoe" in party_text:
        return "KPÖ"
    if "övp" in party_text or "oevp" in party_text:
        return "ÖVP"
    if "grüne" in party_text or "gruene" in party_text:
        return "Grüne"
    if "spö" in party_text or "spoe" in party_text:
        return "SPÖ"
    if "freier gemeinderatsklub" in party_text or "freier gemeinderatsklub" in full_text or "freie" in party_text:
        return "KFG"
    if "neos" in party_text:
        return "NEOS"
    if "fpö" in party_text or "fpoe" in party_text:
        return "FPÖ"
    if "ohne klub" in party_text:
        return "ohne Klub"
    return ""


def council_member_name_from_label(label: str) -> str:
    name = re.sub(r"\([^)]*\)", "", label)
    name = re.sub(r"\s+", " ", name).strip(" ,")
    if "," in name:
        last, first = [part.strip(" ,") for part in name.split(",", 1)]
        name = f"{strip_council_name_titles(first)} {last}".strip()
    else:
        name = strip_council_name_titles(name)
    return re.sub(r"\s+", " ", name).strip()


def city_senate_label_has_role(label: str) -> bool:
    return bool(
        re.search(
            r"\b(?:bürgermeisterin|bürgermeisterin-stellvertreterin|vizebürgermeisterin|stadtrat|stadträtin|str|strin)\b",
            label,
            flags=re.IGNORECASE,
        )
    )


def city_senate_member_name_from_label(label: str) -> str:
    name = re.sub(r"\([^)]*\)", "", label)
    name = re.sub(r"\b(?:Bürgermeisterin-Stellvertreterin|Vizebürgermeisterin|Bürgermeisterin|Stadträtin|Stadtrat|StRin|StR)\b\.?", "", name)
    name = re.sub(r"\b(?:Freier Gemeinderatsklub|Gemeinderatsklub)\b", "", name)
    name = re.sub(r"\s+", " ", name).strip(" ,")
    return council_member_name_from_label(name)


def strip_council_name_titles(value: str) -> str:
    title_pattern = (
        r"\b(?:DI\.?\s*in|Dipl\.-Museol\.?\s*in|Dipl\.-Wirtschaftsing\.?\s*in|Dipl\.-Ing\.?\s*in|"
        r"Dipl\.-Ing\.?|Univ\.-Prof\.?\s*in|Mag\.?\s*a|Mag\.?|Dr\.?\s*in|Dr\.?|MBA|MA|MPH|BSc|BA|FH|med\.?|in)\b"
    )
    cleaned = re.sub(title_pattern, "", value)
    cleaned = re.sub(r"\s*\.\s*", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip(" ,")


def fallback_council_group_meta(party: str) -> dict[str, str]:
    return {"name": party, "short_name": party, "color": "#64748b", "text_color": "#ffffff"}


def council_member(name: str, url: str = "") -> dict[str, str]:
    return {"name": name, "url": url}


def civic_service_summary(records: int | None = None) -> dict:
    return {
        "directory_url": GRAZ_OFFICES_URL,
        "phonebook_url": GRAZ_PHONEBOOK_URL,
        "appointments_url": GRAZ_APPOINTMENTS_URL,
        "contact_form_url": GRAZ_CONTACT_FORM_URL,
        "digital_city_url": GRAZ_DIGITAL_CITY_URL,
        "license": GRAZ_WEBSITE_LICENSE,
        "attribution": "Stadt Graz",
        "records": records if records is not None else len(CIVIC_SERVICES),
        "reuse": GRAZ_WEBSITE_REUSE,
    }


COUNCIL_GROUP_META = {
    "KPÖ": {"name": "KPÖ", "short_name": "KPÖ", "color": "#b91c1c", "text_color": "#ffffff", "note": "größter Klub"},
    "ÖVP": {"name": "ÖVP", "short_name": "ÖVP", "color": "#111827", "text_color": "#ffffff"},
    "Grüne": {"name": "GRÜNE", "short_name": "Grüne", "color": "#16a34a", "text_color": "#ffffff"},
    "SPÖ": {"name": "SPÖ", "short_name": "SPÖ", "color": "#dc2626", "text_color": "#ffffff"},
    "KFG": {
        "name": "(Korruptions-)Freier Gemeinderatsklub",
        "short_name": "KFG",
        "color": "#f59e0b",
        "text_color": "#111827",
    },
    "NEOS": {"name": "NEOS", "short_name": "NEOS", "color": "#db2777", "text_color": "#ffffff"},
    "FPÖ": {"name": "FPÖ", "short_name": "FPÖ", "color": "#2563eb", "text_color": "#ffffff"},
    "ohne Klub": {"name": "ohne Klubzugehörigkeit", "short_name": "ohne Klub", "color": "#64748b", "text_color": "#ffffff"},
}


COUNCIL_GROUP_ORDER = {
    "KPÖ": 1,
    "ÖVP": 2,
    "Grüne": 3,
    "SPÖ": 4,
    "KFG": 5,
    "NEOS": 6,
    "FPÖ": 7,
    "ohne Klub": 8,
}


CITY_SENATE_GROUP_ORDER = {
    "KPÖ": 1,
    "ÖVP": 2,
    "Grüne": 3,
    "KFG": 4,
    "SPÖ": 5,
    "NEOS": 6,
    "FPÖ": 7,
    "ohne Klub": 8,
}


COUNCIL_GROUPS = [
    CouncilGroup(
        "KPÖ",
        "KPÖ",
        15,
        "#b91c1c",
        "#ffffff",
        [
            council_member("Thomas Alic"),
            council_member("Christine Braunersreuther"),
            council_member("Metin Deveci"),
            council_member("Christopher Fröch"),
            council_member("Daniela Gamsjäger-Katzensteiner"),
            council_member("Elke Heinrichs"),
            council_member("Miriam Herlicska"),
            council_member("Amrei Läßer"),
            council_member("Kurt Luttenberger"),
            council_member("Sahar Mohsenzada"),
            council_member("Mina Naghibi"),
            council_member("Nenad Savić"),
            council_member("Christian Sikora"),
            council_member("Ulrike Taberhofer"),
            council_member("Philipp Ulrich"),
        ],
        "größter Klub",
    ),
    CouncilGroup(
        "ÖVP",
        "ÖVP",
        13,
        "#111827",
        "#ffffff",
        [
            council_member("Eva Derler"),
            council_member("Barbara Gartner-Hofbauer"),
            council_member("Anna Hopper", "https://www.graz.at/cms/beitrag/10379867/7768635/Gemeinderaetin_Anna_Hopper_OeVP.html"),
            council_member("Markus Huber"),
            council_member("Daisy Kopera"),
            council_member("Marion Kreiner"),
            council_member("Cornelia Leban-Ibrakovic"),
            council_member("Peter Piffl-Percevic"),
            council_member("Sabine Pogner"),
            council_member("Elisabeth Potzinger"),
            council_member("Gerhard Spath"),
            council_member("Stefan Stücklschweiger"),
            council_member("Georg Topf"),
        ],
    ),
    CouncilGroup(
        "GRÜNE",
        "Grüne",
        9,
        "#16a34a",
        "#ffffff",
        [
            council_member("Tristan Ammerer"),
            council_member("Zeynep Aygan-Romaner"),
            council_member("Karl Dreisiebner"),
            council_member("Gerhard Hackenberger"),
            council_member("Christian Kozina-Voit"),
            council_member("Anna-Sophie Slama"),
            council_member("Hannah Vogel"),
            council_member("Alexandra Würz-Stalder"),
            council_member("Manuela Wutte"),
        ],
    ),
    CouncilGroup(
        "SPÖ",
        "SPÖ",
        4,
        "#dc2626",
        "#ffffff",
        [council_member("Arsim Gjergji"), council_member("Manuel Lenartitsch"), council_member("Anna Robosch"), council_member("Daniela Schlüsselberger")],
    ),
    CouncilGroup(
        "(Korruptions-)Freier Gemeinderatsklub",
        "KFG",
        3,
        "#f59e0b",
        "#111827",
        [council_member("Alexis Pascuttini"), council_member("Astrid Schleicher"), council_member("Michael Winter")],
    ),
    CouncilGroup("NEOS", "NEOS", 1, "#db2777", "#ffffff", [council_member("Philipp Pointner")]),
    CouncilGroup("FPÖ", "FPÖ", 1, "#2563eb", "#ffffff", [council_member("Günter Wagner")]),
    CouncilGroup("ohne Klubzugehörigkeit", "ohne Klub", 2, "#64748b", "#ffffff", [council_member("Mario Eustacchio"), council_member("Sabine Reininghaus")]),
]


CITY_SENATE_GROUPS = [
    CitySenateGroup("KPÖ", "KPÖ", 3, "#b91c1c", "#ffffff", [council_member("Elke Kahr"), council_member("Manfred Eber"), council_member("Robert Krotzer")]),
    CitySenateGroup("ÖVP", "ÖVP", 2, "#111827", "#ffffff", [council_member("Kurt Hohensinner"), council_member("Claudia Unger")]),
    CitySenateGroup("GRÜNE", "Grüne", 1, "#16a34a", "#ffffff", [council_member("Judith Schwentner")]),
    CitySenateGroup(
        "(Korruptions-)Freier Gemeinderatsklub",
        "KFG",
        1,
        "#f59e0b",
        "#111827",
        [council_member("Claudia Schönbacher")],
    ),
]


CIVIC_SERVICES = [
    CivicService(
        name="Bürger:innenservice / Kontaktformular",
        category="Bürgerservice",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Zentrale erste Anlaufstelle für Anregungen und Beschwerden an die Stadtverwaltung.",
        services=["Kontaktformular", "Anliegen an die Stadtverwaltung", "Weiterleitung an zuständige Stellen"],
        website=GRAZ_CONTACT_FORM_URL,
        source_url=GRAZ_CONTACT_FORM_URL,
    ),
    CivicService(
        name="Digitales Amt Graz",
        category="Bürgerservice",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Digitale Abwicklung von Behördenwegen und Online-Services der Stadt Graz.",
        services=["Online-Amtswege", "Formulare", "Termin- und Serviceeinstieg"],
        website=GRAZ_DIGITAL_CITY_URL,
        source="digitalestadt.graz.at",
        source_url=GRAZ_DIGITAL_CITY_URL,
    ),
    CivicService(
        name="Amt der Bürgermeisterin",
        category="Stadtregierung & Verwaltung",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Politisch-administrative Anlaufstelle im Bereich der Bürgermeisterin; Detailzuständigkeiten offiziell prüfen.",
        services=["Bürgermeisterin", "Stadtregierung", "Amtskontakt"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Magistratsdirektion",
        category="Stadtregierung & Verwaltung",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Zentrale Verwaltungskoordination des Magistrats; Detailzuständigkeiten offiziell prüfen.",
        services=["Magistrat", "Verwaltungskoordination", "Amtsorganisation"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Präsidialabteilung",
        category="Stadtregierung & Verwaltung",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Verwaltungsbereich für zentrale präsidiale Aufgaben; Detailzuständigkeiten offiziell prüfen.",
        services=["Präsidialangelegenheiten", "Sitzungen", "Verwaltung"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Kommunikation",
        category="Stadtregierung & Verwaltung",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Kommunikations- und Informationsbereich der Stadt Graz.",
        services=["Presse", "Kommunikation", "Information"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Kontrollamt",
        category="Kontrolle & Recht",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Kontroll- und Prüfbereich der Stadt Graz; Berichte und Zuständigkeiten offiziell prüfen.",
        services=["Kontrolle", "Prüfung", "Berichte"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Bürger:innenamt",
        category="Meldewesen & Dokumente",
        address="Schmiedgasse 26, 8010 Graz",
        lat=47.0688,
        lon=15.4397,
        description="Anlaufstelle für Meldewesen, Dokumente und häufige persönliche Behördenwege.",
        services=["Meldewesen", "Reisedokumente", "Passamt", "Urkunden", "Wahlen/Volksbegehren"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Passservice / Reisedokumente",
        category="Meldewesen & Dokumente",
        address="Schmiedgasse 26, 8010 Graz",
        lat=47.0688,
        lon=15.4397,
        description="Orientierungspunkt für Reisepass, Personalausweis und Reisedokumente; Termine und Detailvoraussetzungen offiziell prüfen.",
        services=["Reisepass", "Personalausweis", "Passamt", "Reisedokumente", "Terminvereinbarung"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Bau- und Anlagenbehörde",
        category="Bauen & Wohnen",
        address="Europaplatz 20, 8020 Graz",
        lat=47.0723,
        lon=15.4178,
        description="Behörde für Bau- und Anlagenverfahren im Stadtgebiet.",
        services=["Bauverfahren", "Anlagenverfahren", "Parteienverkehr nach Termin"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Stadtbaudirektion",
        category="Bauen & Wohnen",
        address="Europaplatz 20, 8020 Graz",
        lat=47.0723,
        lon=15.4178,
        description="Koordination städtischer Bau- und Infrastrukturthemen; Detailzuständigkeiten offiziell prüfen.",
        services=["Stadtbau", "Infrastruktur", "Projektkoordination"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Stadtplanungsamt",
        category="Bauen & Wohnen",
        address="Europaplatz 20, 8020 Graz",
        lat=47.0723,
        lon=15.4178,
        description="Zuständig für Stadtplanung, Flächenwidmung und städtebauliche Grundlagen.",
        services=["Stadtplanung", "Flächenwidmung", "Bebauungsplanung"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Stadtvermessungsamt",
        category="Bauen & Wohnen",
        address="Europaplatz 20, 8020 Graz",
        lat=47.0723,
        lon=15.4178,
        description="Fachstelle für Vermessung, Geodaten und städtische Planungsgrundlagen.",
        services=["Vermessung", "Geodaten", "Stadtplan"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Immobilien",
        category="Bauen & Wohnen",
        address="Schillerplatz 4, 8010 Graz",
        lat=47.0733,
        lon=15.4523,
        description="Städtischer Immobilienbereich; konkrete Angebote und Zuständigkeiten offiziell prüfen.",
        services=["Immobilien", "Liegenschaften", "Städtische Objekte"],
        website="https://www.immobilien.graz.at/",
        source="Immobilien Graz",
        source_url="https://www.immobilien.graz.at/",
    ),
    CivicService(
        name="Wohnungsangelegenheiten",
        category="Bauen & Wohnen",
        address="Schillerplatz 4, 8010 Graz",
        lat=47.0733,
        lon=15.4523,
        description="Anlaufstelle für städtische Wohnungsangelegenheiten und Wohnservice.",
        services=["Gemeindewohnungen", "Wohnberatung", "Wohnunterstützung weiterführend prüfen"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Wohnen Graz",
        category="Bauen & Wohnen",
        address="Schillerplatz 4, 8010 Graz",
        lat=47.0733,
        lon=15.4523,
        description="Eigenbetrieb rund um städtisches Wohnen; Detailangebote offiziell prüfen.",
        services=["Wohnen", "Gemeindewohnungen", "Wohnservice"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Sozialamt",
        category="Soziales",
        address="Schmiedgasse 26, 8010 Graz",
        lat=47.0688,
        lon=15.4397,
        description="Zuständig für soziale Unterstützung und Sozialleistungen der Stadt.",
        services=["Sozialleistungen", "Beratung", "Unterstützung in Notlagen"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Jugend und Familie",
        category="Familie & Bildung",
        address="Kaiserfeldgasse 25, 8010 Graz",
        lat=47.0675,
        lon=15.4397,
        description="Service- und Fachstelle für Kinder, Jugendliche und Familien.",
        services=["Familienservice", "Kinder- und Jugendhilfe", "Beratung"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Bildung und Integration",
        category="Familie & Bildung",
        address="Keesgasse 6, 8010 Graz",
        lat=47.0679,
        lon=15.4428,
        description="Zuständig für Bildungsthemen, Kinderbetreuung und Integration.",
        services=["Bildung", "Kinderbetreuung", "Integration"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Gesundheitsamt",
        category="Gesundheit",
        address="Schmiedgasse 26, 8010 Graz",
        lat=47.0688,
        lon=15.4397,
        description="Gesundheitsbehördliche Aufgaben und öffentliche Gesundheitsservices.",
        services=["Gesundheitsbehörde", "Beratung", "Amtsärztliche Themen"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Geriatrische Gesundheitszentren GGZ",
        category="Gesundheit",
        address="Albert-Schweitzer-Gasse 36, 8020 Graz",
        lat=47.0652,
        lon=15.4224,
        description="Gesundheits- und Pflegeeinrichtungen der Stadt Graz.",
        services=["Pflege", "Geriatrie", "Gesundheitsversorgung"],
        website="https://ggz.graz.at/",
        source="GGZ Graz",
        source_url="https://ggz.graz.at/",
    ),
    CivicService(
        name="Krankenfürsorgeanstalt KFA",
        category="Gesundheit",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Krankenfürsorge der Stadt Graz; Anspruch und Leistungen offiziell prüfen.",
        services=["Krankenfürsorge", "Versicherung", "Gesundheitsleistungen"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Straßenamt",
        category="Verkehr & Öffentlicher Raum",
        address="Europaplatz 20, 8020 Graz",
        lat=47.0723,
        lon=15.4178,
        description="Zuständig für Straßen, temporäre Nutzungen und Baustellenthemen im öffentlichen Raum.",
        services=["Straßenverwaltung", "Baustellen", "Sondernutzungen"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Verkehrsplanung",
        category="Verkehr & Öffentlicher Raum",
        address="Europaplatz 20, 8020 Graz",
        lat=47.0723,
        lon=15.4178,
        description="Fachstelle für Verkehrsplanung, Mobilität und Verkehrskonzepte.",
        services=["Verkehrsplanung", "Mobilitätsplanung", "Rad- und Fußverkehr"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Grazer Parkraum- und Sicherheitsservice GPS",
        category="Verkehr & Öffentlicher Raum",
        address="Jakominigürtel 20, 8010 Graz",
        lat=47.0608,
        lon=15.4496,
        description="Service rund um Parkraumüberwachung und kommunale Sicherheitsdienstleistungen.",
        services=["Parkraum", "Sicherheitsservice", "Kontrollen"],
        website="https://www.gps.graz.at/",
        source="GPS Graz",
        source_url="https://www.gps.graz.at/",
    ),
    CivicService(
        name="Umweltamt",
        category="Umwelt",
        address="Schmiedgasse 26, 8010 Graz",
        lat=47.0688,
        lon=15.4397,
        description="Fachstelle für Umwelt, Lärm, Luft und Klima im Zuständigkeitsbereich der Stadt.",
        services=["Umwelt", "Lärm/Luft", "Förderungen und Beratung prüfen"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Grünraum und Gewässer",
        category="Umwelt",
        address="Europaplatz 20, 8020 Graz",
        lat=47.0723,
        lon=15.4178,
        description="Zuständig für städtischen Grünraum, Bäume, Parks und Gewässerthemen.",
        services=["Parks", "Bäume", "Gewässer"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Finanzdirektion",
        category="Abgaben & Finanzen",
        address="Schmiedgasse 26, 8010 Graz",
        lat=47.0688,
        lon=15.4397,
        description="Finanzverwaltung der Stadt Graz; Detailzuständigkeiten offiziell prüfen.",
        services=["Finanzen", "Budget", "Finanzverwaltung"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Gemeindeabgaben",
        category="Abgaben & Finanzen",
        address="Schmiedgasse 26, 8010 Graz",
        lat=47.0688,
        lon=15.4397,
        description="Anlaufstelle für kommunale Abgaben und Gebühren.",
        services=["Gemeindeabgaben", "Gebühren", "Bescheide"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Rechnungswesen",
        category="Abgaben & Finanzen",
        address="Schmiedgasse 26, 8010 Graz",
        lat=47.0688,
        lon=15.4397,
        description="Rechnungswesen der Stadt Graz; Detailzuständigkeiten offiziell prüfen.",
        services=["Rechnungswesen", "Zahlungen", "Finanzverwaltung"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Personalamt",
        category="Stadtregierung & Verwaltung",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Personalbereich des Magistrats; Jobs und Kontaktwege offiziell prüfen.",
        services=["Personal", "Jobs", "Magistrat"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Kulturamt",
        category="Kultur & Sport",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Fachstelle für Kulturangelegenheiten und Kulturförderung.",
        services=["Kultur", "Kulturförderung", "Veranstaltungen"],
        website="https://www.kultur.graz.at/",
        source="Kultur Graz",
        source_url="https://www.kultur.graz.at/",
    ),
    CivicService(
        name="Sportamt",
        category="Kultur & Sport",
        address="Hauptplatz 1, 8010 Graz",
        lat=47.0707,
        lon=15.4386,
        description="Anlaufstelle für Sportförderung, Sportstätten und Sportangelegenheiten.",
        services=["Sport", "Sportförderung", "Sportstätten"],
        website=GRAZ_OFFICES_URL,
    ),
    CivicService(
        name="Wirtschaft",
        category="Wirtschaft",
        address="Schmiedgasse 26, 8010 Graz",
        lat=47.0688,
        lon=15.4397,
        description="Service für Wirtschaft, Betriebsansiedlung und wirtschaftsbezogene Anliegen.",
        services=["Wirtschaftsservice", "Betriebe", "Förderinformationen prüfen"],
        website="https://www.wirtschaft.graz.at/",
        source="Wirtschaft Graz",
        source_url="https://www.wirtschaft.graz.at/",
    ),
    CivicService(
        name="Feuerwehr Graz",
        category="Sicherheit & Notfälle",
        address="Lendplatz 15-17, 8020 Graz",
        lat=47.0739,
        lon=15.4302,
        description="Berufsfeuerwehr und Brandschutzinformationen der Stadt Graz.",
        services=["Notfall/Feuerwehr", "Brandschutz", "Sicherheitshinweise"],
        website="https://feuerwehr.graz.at/",
        source="Feuerwehr Graz",
        source_url="https://feuerwehr.graz.at/",
    ),
    CivicService(
        name="Holding Graz Service",
        category="Kommunale Services",
        address="Andreas-Hofer-Platz 15, 8010 Graz",
        lat=47.0697,
        lon=15.4372,
        description="Kommunale Dienstleistungen wie Öffentlicher Verkehr, Abfall, Wasser und Infrastruktur werden bei der Holding Graz geprüft.",
        services=["Öffentlicher Verkehr", "Abfall", "Wasser/Kanal", "Kundenservice"],
        website="https://www.holding-graz.at/",
        source="Holding Graz",
        source_url="https://www.holding-graz.at/",
        license="nur verlinkt; aktuelle Details offiziell prüfen",
        reuse="Im Viewer nur als Service-Link und kurzer Orientierungshinweis geführt.",
    ),
]
