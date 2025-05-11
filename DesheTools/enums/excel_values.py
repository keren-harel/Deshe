from enum import Enum

class ExcelColumns(Enum):
    TABLE_NAME = "tableName"
    NAME = "name"
    ALIAS = "alias"
    TYPE = "type"
    DOMAIN = "domain"
    DEFAULT_VALUE = "default_value"
    TO_ADD = "to_add"
    EXISTS = "exists"
    COMMON_ERROR = "common_error"

class LayerNameExcel(Enum):
    LINE_REMARKS_DISCUSSION_1 = "line_remarks_discussion_1"
    FINAL_STANDS_ONLINE_TEMPLATE = "final_stands_online_template"
    SURVEY_POINTS = "survey_points"
    KKL_LINE_REMARKS_ONLINE_TEMPLATE = "kkl_line_remarks_online_template"
    LINE_REMARKS_DISCUSSION_2 = "line_remarks_discussion_2"