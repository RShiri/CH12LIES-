"""Single source of truth for canonical slugs and their Hebrew display names.

Canonical (English) slugs are what gets stored in the database and passed
between agents; Hebrew strings are display-only. No other module may define
its own category or verdict labels.
"""
from enum import StrEnum


class Category(StrEnum):
    SECURITY = "security"
    WORLD = "world"
    POLITICAL = "political"
    ELECTIONS = "elections"
    ECONOMY = "economy"


class Verdict(StrEnum):
    TRUE = "True"
    MOSTLY_TRUE = "Mostly True"
    MISLEADING = "Misleading"
    FALSE = "False"


class Channel(StrEnum):
    N12 = "n12"
    CHANNEL13 = "channel13"
    CHANNEL14 = "channel14"


CATEGORY_HE: dict[Category, str] = {
    Category.SECURITY: "ביטחוני",
    Category.WORLD: "בעולם",
    Category.POLITICAL: "פוליטי",
    Category.ELECTIONS: "בחירות",
    Category.ECONOMY: "כלכלה",
}

VERDICT_HE: dict[Verdict, str] = {
    Verdict.TRUE: "אמת",
    Verdict.MOSTLY_TRUE: "נכון ברובו",
    Verdict.MISLEADING: "מטעה",
    Verdict.FALSE: "שקר",
}

CHANNEL_HE: dict[Channel, str] = {
    Channel.N12: "ערוץ 12",
    Channel.CHANNEL13: "ערוץ 13",
    Channel.CHANNEL14: "ערוץ 14",
}

ALLOWED_CATEGORIES: frozenset[str] = frozenset(c.value for c in Category)
ALLOWED_VERDICTS: frozenset[str] = frozenset(v.value for v in Verdict)
