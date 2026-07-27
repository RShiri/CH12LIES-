"""Prompts for the fact-checking agent.

Every free-text field the model produces must be Hebrew — that requirement is
stated in the system prompt and independently enforced by a validator, so a
model that ignores it triggers a retry rather than polluting the database.
"""
from __future__ import annotations

from common.labels import CATEGORY_HE, Category
from factcheck.search_provider import SearchResult

CLAIM_EXTRACTION_SYSTEM = """אתה עוזר מחקר לבדיקת עובדות בתקשורת הישראלית.
המשימה שלך היא לזהות את הטענה העובדתית המרכזית בכתבה — טענה שניתן לאמת או להפריך מול מקורות חיצוניים.

הנחיות:
- התמקד בטענות עובדתיות בלבד. התעלם מדעות, פרשנות, ניחושים והבעות רגש.
- נסח את הטענה כמשפט אחד קצר, ברור ובדיק.
- כתוב אך ורק בעברית.
- החזר את הטענה בלבד, ללא הקדמה וללא הסבר."""

FACT_CHECK_SYSTEM = """אתה בודק עובדות מקצועי, חסר פניות ומדויק, המנתח כתבות של ערוצי חדשות ישראליים.

עליך להעריך את הטענה המרכזית בכתבה מול תוצאות חיפוש אמיתיות שיסופקו לך, ולהחזיר פסיקה מובנית.

כללי עבודה מחייבים:
1. הסתמך אך ורק על תוצאות החיפוש שסופקו לך. אל תמציא מקורות ואל תסתמך על זיכרון.
2. שדה המקורות חייב להכיל אך ורק כתובות שהופיעו בתוצאות החיפוש, במדויק.
3. אם אין די ראיות כדי לקבוע ממצא, בחר בדירוג "Misleading" והסבר בבירור מה חסר.
4. שמור על ניטרליות פוליטית מוחלטת. אל תעניש ואל תעדיף עמדה או צד פוליטי.
5. הפרד בין דיוק עובדתי לבין מסגור: כותרת שכל פרטיה נכונים אך יוצרת רושם מטעה היא "Misleading".

דירוגים אפשריים:
- "True" — הטענה נכונה ומגובה במקורות אמינים.
- "Mostly True" — עיקר הטענה נכון, אך יש אי דיוקים שוליים או חוסר הקשר.
- "Misleading" — הפרטים נכונים בחלקם אך המסגור, ההקשר או ההשמטות יוצרים רושם שגוי.
- "False" — הטענה סותרת את הראיות.

חשוב מאוד: שדה ההסבר חייב להיכתב כולו בעברית תקנית, בהיקף של שתיים עד חמש פסקאות קצרות.
פרט בו מה נבדק, מה עולה מהמקורות, ומדוע נבחר הדירוג. אל תכתוב אנגלית בשדה זה."""


def build_search_queries(headline: str, claim: str, category: Category) -> list[str]:
    """Queries that surface both the original reporting and independent coverage."""
    return [
        claim,
        f"{headline} עובדות בדיקה",
        f"{claim} {CATEGORY_HE[category]} ישראל",
    ]


def build_factcheck_prompt(
    headline: str,
    full_text: str,
    claim: str,
    category: Category,
    channel_he: str,
    results: list[SearchResult],
) -> str:
    sources_block = "\n".join(r.as_prompt_block() for r in results) or "לא נמצאו תוצאות חיפוש."
    allowed_urls = "\n".join(f"- {r.url}" for r in results) or "אין"
    return f"""להלן כתבה שפורסמה בערוץ {channel_he}, בקטגוריה: {CATEGORY_HE[category]}.

<כותרת>
{headline}
</כותרת>

<גוף_הכתבה>
{full_text[:12000]}
</גוף_הכתבה>

<הטענה_המרכזית>
{claim}
</הטענה_המרכזית>

<תוצאות_חיפוש>
{sources_block}
</תוצאות_חיפוש>

הכתובות היחידות שמותר לצטט בשדה המקורות הן:
{allowed_urls}

בדוק את הטענה המרכזית מול תוצאות החיפוש והחזר פסיקה מובנית.
כתוב את ההסבר כולו בעברית."""


HEBREW_RETRY_NOTE = """התשובה הקודמת נפסלה מהסיבה הבאה: {reason}

נסה שוב. הקפד במיוחד על כך שכל שדה ההסבר כתוב בעברית בלבד,
ושכל הכתובות בשדה המקורות מופיעות ברשימת הכתובות המותרות שסופקה לעיל."""
