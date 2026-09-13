import ee


def calculate_vegetation_cover(image, vegetation_bands):
    """
    Calculate total vegetation cover from selected bands.
    """

    return (
        image
        .select(vegetation_bands)
        .reduce(ee.Reducer.sum())
        .rename("vegetation_cover")
    )


def calculate_vegetation_change(
    raster_before,
    raster_after,
    vegetation_bands_before,
    vegetation_bands_after
):

    vegetation_before = (
        raster_before
        .select(vegetation_bands_before)
        .reduce(ee.Reducer.sum())
        .rename("vegetation_before")
    )

    vegetation_after = (
        raster_after
        .select(vegetation_bands_after)
        .reduce(ee.Reducer.sum())
        .rename("vegetation_after")
    )

    vegetation_change = (
        vegetation_after
        .subtract(vegetation_before)
        .toDouble()
        .rename("vegetation_change")
    )

    return vegetation_change
def identify_thinning(change, threshold=15):
    """
    Identify pixels where vegetation cover decreased
    by more than the threshold.
    """

    return (
        change
        .lt(-threshold)
        .rename("thinning")
    )