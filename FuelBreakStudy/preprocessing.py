import ee

def create_buffer(study_area, distance):
    """
    Create a buffer around the input geometry.
    """

    return study_area.geometry().buffer(distance)


def apply_focal_mean(image, radius=15):
    """
    Apply a moving mean while keeping the original
    raster resolution.
    """

    return image.focal_mean(
        radius=radius,
        units="meters"
    )


def clip_to_buffer(image, buffer):
    """
    Clip raster to the analysis buffer.
    """

    return image.clip(buffer)

def aggregate_to_mega_pixels(image, scale=30):
    """
    Aggregate a 10 m raster into 30 m mega pixels.

    Each 30 m pixel is calculated as the mean
    of the underlying 10 m pixels.
    """

    mega_pixels = image.reduceResolution(
        reducer=ee.Reducer.mean(),
        maxPixels=9
    ).reproject(
        crs=image.projection(),
        scale=scale
    )

    return mega_pixels