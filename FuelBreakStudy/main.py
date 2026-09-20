import config
import preprocessing
import analysis
import gee_utils


STUDY_AREA_ASSET = config.STUDY_AREA_ASSET

RASTER_BEFORE_ASSET = config.RASTER_2018
RASTER_AFTER_ASSET = config.RASTER_2020


def run_analysis():

    # ========================================================
    # 1. Load study area
    # ========================================================

    study_area = gee_utils.load_study_area(
        STUDY_AREA_ASSET
    )


    # ========================================================
    # 2. Create 200 m buffer
    # ========================================================

    buffer = preprocessing.create_buffer(
        study_area,
        config.BUFFER_DISTANCE
    )


    # ========================================================
    # 3. Load rasters
    # ========================================================

    raster_before_original = gee_utils.load_raster(
        RASTER_BEFORE_ASSET
    )

    raster_after_original = gee_utils.load_raster(
        RASTER_AFTER_ASSET
    )


    # ========================================================
    # 4. Apply moving mean
    # ========================================================

    if config.USE_MEGA_PIXELS:

        raster_before = preprocessing.aggregate_to_mega_pixels(
            raster_before_original,
            config.MEGA_PIXEL_SIZE
        )

        raster_after = preprocessing.aggregate_to_mega_pixels(
            raster_after_original,
            config.MEGA_PIXEL_SIZE
        )

    else:

        raster_before = raster_before_original
        raster_after = raster_after_original


    # ========================================================
    # 5. Clip all rasters to 200 m buffer
    # ========================================================

    raster_before = preprocessing.clip_to_buffer(
        raster_before,
        buffer
    )

    raster_after = preprocessing.clip_to_buffer(
        raster_after,
        buffer
    )


    # ========================================================
    # 6. Vegetation change
    # ========================================================

    change = analysis.calculate_vegetation_change(
        raster_before,
        raster_after,
        config.VEGETATION_BANDS_BEFORE,
        config.VEGETATION_BANDS_AFTER
    )


    # ========================================================
    # 8. Identify thinning
    # ========================================================

    thinning = analysis.identify_thinning(
        change,
        config.CHANGE_THRESHOLD
    )

    # ========================================================
    # 9. Mean vegetation growth in thinning pixels
    # ========================================================

    # ==========================================
    # 9. Calculate mean vegetation growth
    #    only on thinning pixels
    # ==========================================
    annual_images = gee_utils.load_annual_images(
        config.ANNUAL_RASTERS,
        config.VEGETATION_BANDS_BY_YEAR
    )

    mean_vegetation_growth = (
        analysis.calculate_mean_vegetation_growth(
            annual_images,
            thinning
        )
    )


    # ========================================================
    # Return products
    # ========================================================

    return {
        "buffer": buffer,
        "change": change,
        "thinning": thinning,

        "mean_vegetation_growth": mean_vegetation_growth
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    gee_utils.initialize_gee(
        config.PROJECT_ID
    )

    results = run_analysis()

    gee_utils.export_analysis_results(
        results,
        "EarthEngineExports",
        config.EXPORT_SCALE
    )

    print("Analysis completed.")