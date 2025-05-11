from enum import Enum

class Suggestion(Enum):
    UNION = "איחוד"
    SPLIT = "פיצול"

class Decision(Enum):
    YES = "כן"
    NO = "לא"
    SURVEYOR_DECISION = "?"

class surveyDecision(Enum):
    APPROVE = "לקבל"
    REJECT = "לא לקבל"

class Notes(Enum):
    FIELD_SUGGESTION = "הצעה מהשטח"
    NEW_SUGGESTION = "הצעה חדשה"
    PRE_MAPPING_SUGGESTION_APPROVED = "הצעה מקדם מיפוי – התקבלה"
    PRE_MAPPING_SUGGESTION_REJECTED = "הצעה מקדם מיפוי – נדחתה"
    SECOND_DISCUSSION_SUGGESTION = "הצעה מהכנה לדיון שני"
