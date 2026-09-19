PROJECT_ID = "ee-kerengoldkg"

STUDY_AREA_ASSET = r"projects/ee-kerengoldkg/assets/beitar_buffer_zone_line"


RASTER_2018 = r"projects/ee-kerengoldkg/assets/2017/ReashonHebron_17"
RASTER_2019 = r"projects/ee-kerengoldkg/assets/2018/ReashonHebron_18"
RASTER_2020 = r"projects/ee-kerengoldkg/assets/2019/ReashonHebron_19"
RASTER_2021 = r"projects/ee-kerengoldkg/assets/2020/ReashonHebron_20"
RASTER_2022 = r"projects/ee-kerengoldkg/assets/2021/ReashonHebron_21"
RASTER_2023 = r"projects/ee-kerengoldkg/assets/2022/ReashonHebron_22"
RASTER_2024 = r"projects/ee-kerengoldkg/assets/ReashonHebron_23"
RASTER_2025 = r"projects/ee-kerengoldkg/assets/2024/ReashonHebron_24"

USE_MEGA_PIXELS = False

BUFFER_DISTANCE = 200 ## meter

CHANGE_THRESHOLD = 20

FOCAL_RADIUS = 15

MEGA_PIXEL_SIZE = 30

EXPORT_SCALE = 30 if USE_MEGA_PIXELS else 10

VEGETATION_BANDS_BEFORE = ["b6"]

VEGETATION_BANDS_AFTER = ["b6"]