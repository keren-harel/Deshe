
# -*- coding: utf-8 -*-
from enum import Enum

# =========================================
# ENUM DEFINITIONS WITH RELATIVE FACTORS
# =========================================
# Each score is defined as a factor:
# MAXIMUM = 1.0 (full score)
# MEDIUM = 0.5 (half score)
# LOW = 1/3 (one-third score)
# NONE = 0.0 (no score)
# The actual numeric score will be calculated dynamically:
# final_score = max_possible_score * factor
# =========================================

class DynamicScore(Enum):
    MAXIMUM = 1.0      # Full score
    MEDIUM = 0.5       # Half score
    LOW = 1/3      # One-third score
    NONE = 0.0          # No score

class spatialScaleScores(Enum):
    """
    ציון משוקלל עבור כל סקאלה מרחבית
    """
    NATIONAL = 30
    Agricultural_Landscape_Unit = 45
    Natural_Features = 15
    Agricultural_Features = 10

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


class CoverTypeScore(Enum):
    """
    ציון סוג כיסוי קרקע
    """
    HIGH = 5
    LOW = 0

class CoverType(Enum):
    """
    סוג כיסוי קרקע
    """
    OPEN = ("שטח פתוח", "גידולי שדה", "מטעים", "גדש")
    COVER = ("בתי רשת", "מנהרות", "רשת", "כיסוי רשת")


class WaterTypeScore(Enum):
    """
    ציון סוג השקיה
    """
    HIGH = 5      # גידולי בעל ללא השקיה
    LOW = 0       # גידולים מושקים - שלחין

class WaterType(Enum):
    """
    סוג השקיה
    """
    SHELACHIN = ("מליחים", "שלחין", "קולחין", "שפירים", "מעורב")
    BAAL = ("בעל", "ללא השקיה", "גשם")
    OTHER = ("", "לא ידוע","לא רלוונטי","לא רלונטי", None)
