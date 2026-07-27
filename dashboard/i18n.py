"""Every user-facing string in the dashboard, in Hebrew.

Components read from here rather than embedding literals, so wording changes in
one place and nothing drifts between tabs.
"""
from __future__ import annotations

UI = {
    # chrome
    "page_title": "מדד שקר — בדיקת עובדות בערוצי החדשות",
    "app_title": "מדד שקר",
    "app_subtitle": "בדיקת עובדות אוטומטית לכתבות חדשות בישראל",
    # tabs
    "tab_feed": "פיד בדיקות",
    "tab_index": "מדד שקר",
    "tab_categories": "פילוח לפי נושא",
    "tab_how": "איך המערכת עובדת",
    # sidebar / filters
    "filters": "סינון",
    "filter_channel": "ערוץ",
    "filter_category": "נושא",
    "filter_verdict": "דירוג",
    "filter_days": "טווח זמן (ימים אחורה)",
    "filter_limit": "מספר כתבות להצגה",
    "filter_all": "הכל",
    "refresh": "רענון נתונים",
    # feed
    "feed_title": "כתבות שנבדקו לאחרונה",
    "feed_empty": "לא נמצאו כתבות התואמות את הסינון שבחרת.",
    "feed_no_screenshot": "לא נשמר צילום מסך עבור כתבה זו.",
    "feed_explanation": "הסבר הבדיקה",
    "feed_sources": "מקורות",
    "feed_open_article": "פתיחת הכתבה המקורית",
    "feed_table_view": "תצוגת טבלה",
    "feed_table_hint": "טבלה מסכמת של אותן כתבות, לקריאה מהירה ולנגישות.",
    # lie index
    "index_title": "מדד שקר לפי ערוץ",
    "index_current": "מדד נוכחי",
    "index_checked": "כתבות שנבדקו",
    "index_trend": "מגמת מדד השקר לאורך זמן",
    "index_no_data": "אין עדיין מספיק נתונים לחישוב המדד.",
    "index_scale_low": "אמין",
    "index_scale_high": "בעייתי",
    "index_axis": "מדד שקר",
    "index_axis_time": "תאריך",
    # categories
    "cat_title": "התפלגות הדירוגים בחמשת הנושאים",
    "cat_count_axis": "מספר כתבות",
    "cat_axis": "נושא",
    "cat_share_title": "שיעור הכתבות הבעייתיות בכל נושא",
    "cat_share_axis": "שיעור מטעה או שקרי",
    "cat_no_data": "אין עדיין נתונים להצגה בפילוח לפי נושא.",
    "legend_verdict": "דירוג",
}

#: The five categories the system covers, for the explanatory tab.
COVERED_CATEGORIES_NOTE = (
    "המערכת בודקת אך ורק חמישה נושאים: ביטחוני, בעולם, פוליטי, בחירות וכלכלה. "
    "כתבות בנושאי ספורט, בידור, רכילות או טכנולוגיה נזרקות כבר בשלב האיסוף ואינן נכנסות למאגר."
)
