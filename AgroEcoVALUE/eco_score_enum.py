
# -*- coding: utf-8 -*-
from enum import Enum

class CorridorScore(Enum):
    """
    מסדרון אקולוגי ארצי או אזורי
    """
    CORE = (15, "ליבה", "שמורת טבע/גן לאומי/יער קקל")
    TRANSITION = (10, "מעבר", "מעבר הכרחי - צוואר בקבוק")
    CORRIDOR = (5, "מסדרון", "מסדרון אקולוגי ארצי/אזורי")
    NONE = (0, "אין חפיפה", "מחוץ למסדרון אקולוגי ארצי/אזורי")

class FloodplainScore(Enum):
    """
    פשט הצפה
    """
    MAXIMUM = 15  # Parcel is inside floodplain
    MEDIUM = 8    # Parcel is within max_distance from floodplain
    LOW = 0       # Parcel is farther than max_distance from floodplain

class NaturalAreaType(Enum):
    """
    סוג שטח טבעי
    """
    OPEN = ("פתוח", "מוגן")
    AGRICULTURAL = ("חקלאי", "")

class NaturalAreaScore(Enum):
    """
    ציון שטח טבעי
    """
    MAXIMUM = 15
    MEDIUM = 8
    LOW = 0 

class OpenSpaceCorridorType(Enum):
    """
    סיווג רצף שטחים פתוחים
    """
    CORE = (4, 5)           # ערכיות רצף גבוהה מאוד-מירבית
    BUFFER = (2, 3)         # ערכיות רצף בינונית-גבוהה
    DISTURBANCE = (0, 1)    # ערכיות רצף נמוכה

class OpenSpaceCorridorScore(Enum):
    """
    ציון ערכיות רצף שטחים פתוחים
    """
    CORE = 15             # החלקה או חלק ממנה נמצאים בליבה  של רצף שטחים פתוחים
    BUFFER = 8            # החלקה או חלק ממנה נמצאים באזור חיץ
    DISTURBANCE = 0       # החלקה או חלק ממנה צמודים להפרה