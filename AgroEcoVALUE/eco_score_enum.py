
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
    LOW = 1/3       # One-third score
    NONE = 0.0          # No score

class spatialScaleScores(Enum):
    """
    ציון משוקלל עבור כל סקאלה מרחבית
    """
    NATIONAL = 30
    Agricultural_Landscape_Unit = 45
    Natural_Features = 15
    Agricultural_Features = 10

class CorridorScore(Enum):  #! <----- צריך לשנות מציון לסוג
    """
    מסדרון אקולוגי ארצי או אזורי
    """
    CORE = ("ליבה", "יער", "שמורות", "גנים", "יערות", "שמורה")
    TRANSITION = ("מעבר", "מעבר הכרחי - צוואר בקבוק", "מעבר אקולוגי",   "מעבר אקולוגי אזורי")
    CORRIDOR = ("מסדרון", "מסדרון אקולוגי ארצי/אזורי", "רצף שטחים פתוחים",  "שטח פתוח רציף")
    NONE = ("", "לא רלוונטי", "לא ידוע", "לא רלונטי", None)

class NaturalAreaType(Enum):
    """
    סוג שטח טבעי
    """
    OPEN = ("פתוח", "מוגן")
    AGRICULTURAL = ("חקלאי", "")

class OpenSpaceCorridorType(Enum):
    """
    סיווג רצף שטחים פתוחים
    """
    CORE = (4, 5)           # ערכיות רצף גבוהה מאוד-מירבית
    BUFFER = (2, 3)         # ערכיות רצף בינונית-גבוהה
    DISTURBANCE = (0, 1)    # ערכיות רצף נמוכה

class CoverType(Enum):
    """
    סוג כיסוי קרקע
    """
    OPEN = ("שטח פתוח", "גידולי שדה", "מטעים", "גדש")
    COVER = ("בתי רשת", "מנהרות", "רשת", "כיסוי רשת")

class WaterType(Enum):
    """
    סוג השקיה
    """
    SHELACHIN = ("מליחים", "שלחין", "קולחין", "שפירים", "מעורב")
    BAAL = ("בעל", "ללא השקיה", "גשם")
    OTHER = ("", "לא ידוע","לא רלוונטי","לא רלונטי", None)
