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


def calculate_vegetation_recovery_metrics(
        annual_images,
        thinning,
        tree_pre,
        tree_t0,
):
    """
    Calculate three vegetation recovery metrics for thinned pixels.
    """

    # Sort annual images by year
    annual_images = annual_images.sort("year")

    # Select the tree-cover band for each year




    # Sort again after selecting bands
    annual_images = annual_images.sort("year")

    images_list = annual_images.toList(annual_images.size())

    # First and last images
    first_image = ee.Image(images_list.get(0))
    last_image = ee.Image(
        images_list.get(annual_images.size().subtract(1))
    )

    tree_pre = tree_pre.rename("tree_pre")
    tree_t0 = tree_t0.rename("tree_t0")
    tree_current = last_image.rename("tree_current")

    # --------------------------------------------------
    # 1. Recovery Score
    # --------------------------------------------------

    denominator = tree_pre.subtract(tree_t0)

    recovery_score = (
        tree_current.subtract(tree_t0)
        .divide(denominator)
        .multiply(100)
        .rename("recovery_score")
        .updateMask(denominator.neq(0))
    )

    # --------------------------------------------------
    # 2. Growth Trend
    # --------------------------------------------------

    changes = ee.ImageCollection.fromImages(
        ee.List.sequence(
            1,
            annual_images.size().subtract(1)
        ).map(
            lambda i: (
                ee.Image(images_list.get(i))
                .subtract(
                    ee.Image(
                        images_list.get(
                            ee.Number(i).subtract(1)
                        )
                    )
                )
                .rename("annual_change")
            )
        )
    )

    growth_trend = changes.mean().rename("growth_trend")

    # --------------------------------------------------
    # 3. Consistency
    # --------------------------------------------------

    positive_changes = changes.map(
        lambda image: image.gt(0).rename("positive_change")
    )

    consistency = (
        positive_changes.sum()
        .divide(changes.count())
        .multiply(100)
        .rename("consistency")
    )

    # --------------------------------------------------
    # Combine metrics and mask to thinning pixels
    # --------------------------------------------------

    metrics = (
        recovery_score
        .addBands(growth_trend)
        .addBands(consistency)
        .updateMask(thinning.eq(1))
    )

    return metrics