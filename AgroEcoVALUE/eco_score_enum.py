
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

class NaturalArea_type(Enum):
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
