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

def calculate_mean_vegetation_growth(
    images,
    thinning
):
    """
    Calculate the mean annual percentage change in vegetation
    for pixels identified as thinning.

    The percentage change is calculated between consecutive years:

        ((after - before) / before) * 100

    Pixels where the vegetation value in the previous year is 0
    are excluded from the calculation.

    Parameters
    ----------
    images : ee.ImageCollection
        Annual vegetation rasters. Each image must contain
        a band named 'vegetation' and a 'year' property.

    thinning : ee.Image
        Binary raster where:
            1 = thinning pixel
            0 = non-thinning pixel

    Returns
    -------
    ee.Image
        Raster containing the mean annual percentage vegetation
        change for thinning pixels.
    """

    # Sort images chronologically
    images = images.select(["vegetation"]).sort("year")

    image_list = images.toList(images.size())
    n_images = images.size()

    # Calculate percentage change between consecutive years
    def calculate_change(i):

        i = ee.Number(i)

        before = ee.Image(image_list.get(i))
        after = ee.Image(image_list.get(i.add(1)))

        before_value = before.select("vegetation")
        after_value = after.select("vegetation")

        # Avoid division by zero
        valid = before_value.neq(0)

        change_percent = (
            after_value
            .subtract(before_value)
            .divide(before_value)
            .multiply(100)
            .updateMask(valid)
            .rename("change_percent")
        )

        return change_percent

    # Create an ImageCollection of annual percentage changes
    changes = ee.ImageCollection(
        ee.List.sequence(
            0,
            n_images.subtract(2)
        ).map(calculate_change)
    )

    # Calculate mean annual change
    mean_growth = (
        changes
        .mean()
        .rename("mean_vegetation_growth")
    )

    # Keep only thinning pixels
    mean_growth = mean_growth.updateMask(
        thinning.eq(1)
    )

    return mean_growth