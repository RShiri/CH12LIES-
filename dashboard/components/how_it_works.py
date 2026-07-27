"""The "איך המערכת עובדת" tab.

Written for a reader with no background in programming or data — the pipeline
explained with everyday analogies rather than terminology. Every string here is
Hebrew by design; this is the one place in the codebase where long-form Hebrew
prose lives, so it is kept together rather than split across the i18n dict.
"""
from __future__ import annotations

from common.labels import CATEGORY_HE, VERDICT_HE, Verdict

TITLE = "איך המערכת עובדת?"

INTRO = """המערכת הזו בודקת אם מה שנכתב בכתבות חדשות הוא נכון.
היא עושה זאת באופן אוטומטי, יום אחרי יום, בלי שאדם צריך לקרוא כל כתבה בעצמו.
בעמוד הזה נסביר את כל התהליך בשפה פשוטה, שלב אחר שלב.
אין צורך בשום ידע קודם במחשבים כדי להבין אותו."""

STEPS = [
    {
        "title": "שלב 1: איסוף הכתבות",
        "body": """דמיינו אדם שכל בוקר נכנס לאתר החדשות, עובר על הכותרות,
        ומצלם כל כתבה שמעניינת אותו כדי שיישאר לו תיעוד.
        זה בדיוק מה שהמערכת עושה, רק הרבה יותר מהר.

        המערכת פותחת את אתר החדשות בדפדפן, קוראת את הכותרות ואת גוף הכתבות,
        ושומרת צילום מסך של כל כתבה. הצילום חשוב מאוד:
        אם הכתבה תשונה או תימחק מאוחר יותר, התיעוד המקורי עדיין יישמר אצלנו.

        המערכת גם יודעת ללכת אחורה בזמן ולאסוף כתבות מהחודש האחרון,
        כדי שיהיה בסיס נתונים משמעותי כבר מההתחלה.""",
    },
    {
        "title": "שלב 2: סינון לחמישה נושאים בלבד",
        "body": f"""לא כל כתבה נכנסת לבדיקה. המערכת מתמקדת אך ורק בחמישה נושאים:
        {", ".join(CATEGORY_HE.values())}.

        אפשר לחשוב על זה כמו על שומר בכניסה שמחזיק רשימה קצרה.
        כתבה על ספורט, על בידור, על רכילות או על גאדג׳טים חדשים פשוט לא נכנסת בדלת,
        ולכן היא גם לא מגיעה לבדיקה ולא נשמרת במאגר.

        הסינון הזה נעשה פעמיים, ליתר ביטחון: פעם אחת בשלב האיסוף,
        ופעם נוספת ברגע השמירה במאגר. כך כתבה שאינה באחד מחמשת הנושאים
        לא יכולה להיכנס פנימה בטעות.""",
    },
    {
        "title": "שלב 3: בדיקת העובדות",
        "body": """כאן נמצא הלב של המערכת. אפשר לדמיין תחקירן זהיר שיושב מול הכתבה
        ושואל את עצמו שאלה אחת: מה בעצם נטען כאן, ואיך אפשר לבדוק אם זה נכון?

        התהליך מתרחש בשלושה חלקים קטנים.
        ראשית, המערכת מזהה את הטענה המרכזית בכתבה — המשפט שאפשר לבדוק מולו עובדות,
        ולא דעה או פרשנות.
        שנית, היא מחפשת באינטרנט מקורות נוספים שמדברים על אותו נושא.
        שלישית, היא משווה בין מה שנכתב בכתבה לבין מה שעולה מהמקורות שנמצאו.

        יש כאן כלל נוקשה אחד: מותר לצטט רק מקורות שנמצאו בפועל בחיפוש.
        המערכת לא יכולה להמציא קישור או להסתמך על משהו שהיא ״זוכרת״.
        אם המקור לא הופיע בתוצאות החיפוש, הוא נפסל אוטומטית והבדיקה נעשית מחדש.""",
    },
]

VERDICT_EXPLANATIONS: dict[Verdict, str] = {
    Verdict.TRUE: "הטענה נכונה ומגובה במקורות אמינים.",
    Verdict.MOSTLY_TRUE: "עיקר הטענה נכון, אך יש אי דיוקים קטנים או חוסר בהקשר.",
    Verdict.MISLEADING: "הפרטים נכונים בחלקם, אבל האופן שבו הם מוצגים יוצר רושם שגוי.",
    Verdict.FALSE: "הטענה סותרת את הראיות שנמצאו.",
}

VERDICT_INTRO = """בסוף הבדיקה כל כתבה מקבלת אחד מארבעה דירוגים,
ולצידו הסבר מפורט בעברית שמפרט מה נבדק ומדוע נבחר הדירוג הזה."""

MISLEADING_NOTE = """שימו לב במיוחד לדירוג ״מטעה״. זהו המקרה המעניין ביותר,
משום שכל פרט בכתבה יכול להיות נכון בפני עצמו, ובכל זאת התמונה המתקבלת שגויה.
לדוגמה, כותרת שמציינת נתון אמיתי אך משמיטה את ההקשר שמסביר אותו."""

INDEX_TITLE = "שלב 4: חישוב מדד השקר"

INDEX_BODY = """מדד השקר הוא ציון אחד שמסכם את מידת האמינות של ערוץ לאורך זמן.
הציון נע בין 0 ל־1: ככל שהוא נמוך יותר, הערוץ אמין יותר.

הרעיון פשוט. כל דירוג מקבל ניקוד משלו, ואז מחשבים ממוצע של כל הכתבות שנבדקו.
ככה זה עובד בפועל:"""

INDEX_WEIGHTS_NOTE = """כלומר כתבה שדורגה כשקר תורמת נקודה שלמה למדד,
כתבה מטעה תורמת יותר מחצי נקודה, וכתבה נכונה לא תורמת כלום."""

INDEX_EXAMPLE = """ניקח דוגמה קטנה. נניח שערוץ מסוים פרסם עשר כתבות שנבדקו:
שש דורגו כאמת, שתיים כנכונות ברובן, אחת כמטעה ואחת כשקר.

הניקוד המצטבר הוא אפס נקודות מהאמת, ארבע עשיריות מהשתיים הנכונות ברובן,
שש עשיריות מהמטעה ונקודה אחת מהשקר. סך הכול שתי נקודות.
מחלקים בעשר הכתבות ומקבלים מדד של 0.2, כלומר ערוץ אמין יחסית."""

INDEX_RECENCY = """יש עוד דבר אחד חשוב: כתבות חדשות נחשבות יותר מכתבות ישנות.
מה שפורסם השבוע משפיע על המדד יותר ממה שפורסם לפני חודש.
הסיבה היא שאנחנו רוצים לדעת מה מצב הערוץ עכשיו, ולא לפני שנה.
בפועל, המשקל של כתבה נחתך בחצי בערך כל שבועיים.

בזכות זה אפשר לראות בגרף מגמה אמיתית: אם ערוץ משתפר, המדד שלו יורד עם הזמן."""

LIMITS_TITLE = "מה המערכת לא עושה"

LIMITS = [
    "המערכת בודקת את הטענה המרכזית בכל כתבה, ולא כל משפט ומשפט שנכתב בה.",
    "המערכת יכולה לטעות. היא כלי עזר לקורא, ולא פסיקה סופית או תחליף לשיקול דעת אנושי.",
    "איכות הבדיקה תלויה במקורות שנמצאו. בנושא שכמעט לא סוקר, יהיה קשה יותר להגיע למסקנה ברורה.",
    "המערכת לא מדרגת דעות, פרשנות או תחזיות — רק טענות עובדתיות שאפשר לבדוק.",
    "המערכת אינה מזהה כוונה. היא בודקת אם נאמר דבר נכון, ולא מדוע הוא נאמר.",
]

CLOSING = """כל הכתבות, הדירוגים וההסברים גלויים לעיון בלשונית ״פיד בדיקות״,
יחד עם צילום המסך של הכתבה המקורית והקישורים למקורות שעליהם התבססה הבדיקה.
כך אפשר תמיד לבדוק את הבדיקה עצמה."""


def _paragraphs(text: str) -> str:
    """Turn a block of prose into HTML paragraphs, collapsing source indentation."""
    blocks = [" ".join(part.split()) for part in text.strip().split("\n\n")]
    return "".join(f"<p>{block}</p>" for block in blocks if block)


def render(st, weights: dict[str, float] | None = None) -> None:
    from dashboard.theme import VERDICT_COLOR, VERDICT_ORDER

    weights = weights or {"True": 0.0, "Mostly True": 0.2, "Misleading": 0.6, "False": 1.0}

    st.subheader(TITLE)
    st.markdown(f'<div class="how-note">{_paragraphs(INTRO)}</div>', unsafe_allow_html=True)
    st.write("")

    for step in STEPS:
        st.markdown(
            f'<div class="how-step"><h4>{step["title"]}</h4>{_paragraphs(step["body"])}</div>',
            unsafe_allow_html=True,
        )

    # Verdicts, each with its colour swatch alongside the written label.
    rows = "".join(
        f'<p><span class="badge" style="background:{VERDICT_COLOR[v]}">{VERDICT_HE[v]}</span>'
        f" — {VERDICT_EXPLANATIONS[v]}</p>"
        for v in VERDICT_ORDER
    )
    st.markdown(
        f'<div class="how-step"><h4>ארבעת הדירוגים</h4>'
        f"{_paragraphs(VERDICT_INTRO)}{rows}{_paragraphs(MISLEADING_NOTE)}</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="how-step"><h4>{INDEX_TITLE}</h4>{_paragraphs(INDEX_BODY)}</div>',
        unsafe_allow_html=True,
    )
    st.table(
        [
            {"דירוג": VERDICT_HE[v], "ניקוד למדד": f"{weights.get(v.value, 0):g}"}
            for v in VERDICT_ORDER
        ]
    )
    st.markdown(
        f'<div class="how-step">{_paragraphs(INDEX_WEIGHTS_NOTE)}'
        f"{_paragraphs(INDEX_EXAMPLE)}{_paragraphs(INDEX_RECENCY)}</div>",
        unsafe_allow_html=True,
    )

    limits = "".join(f"<li>{item}</li>" for item in LIMITS)
    st.markdown(
        f'<div class="how-step"><h4>{LIMITS_TITLE}</h4>'
        f'<ul class="source-list">{limits}</ul></div>',
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="how-note">{_paragraphs(CLOSING)}</div>', unsafe_allow_html=True)
