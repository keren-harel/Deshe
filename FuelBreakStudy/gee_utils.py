import ee

def initialize_gee(project_id):
    """
    Authenticate and initialize Google Earth Engine.
    """

    ee.Authenticate()
    ee.Initialize(project=project_id)


def load_study_area(asset_id):
    """
    Load the input geometry.
    """

    study_area = ee.FeatureCollection(asset_id)

    return study_area

def load_raster(asset_id):
    """
    Load an Earth Engine raster.
    """

    return ee.Image(asset_id)

def export_raster(
    image,
    description,
    folder,
    region,
    scale=10,
    crs=None
):
    """
    Export an Earth Engine image to Google Drive.

    Masked pixels are exported as -9999.
    """

    # Convert masked pixels to NoData value
    image = image.unmask(-9999)

    export_params = {
        "image": image,
        "description": description,
        "folder": folder,
        "region": region,
        "scale": scale,
        "maxPixels": 1e13,
        "fileFormat": "GeoTIFF"
    }

    if crs is not None:
        export_params["crs"] = crs

    task = ee.batch.Export.image.toDrive(
        **export_params
    )

    task.start()

    print(f"Export started: {description}")

    return task
def export_analysis_results(results, folder, scale=10):
    """
    Export all analysis raster products to Google Drive.

    Parameters
    ----------
    results : dict
        Dictionary containing the analysis products.

    folder : str
        Name of the Google Drive folder where the files
        will be exported.

    scale : int
        Pixel size of the exported rasters in meters.
    """

    region = results["buffer"]

    products = {
        "vegetation_change_trees": results["change"],
        "thinning": results["thinning"],
        "mean_vegetation_growth": results["mean_vegetation_growth"]
    }

    tasks = []

    for description, image in products.items():

        task = export_raster(
            image=image,
            description=description,
            folder=folder,
            region=region,
            scale=scale
        )

        tasks.append(task)

    return tasks

def load_annual_images(raster_assets, vegetation_bands_by_year):

    images = []

    for year, asset_id in raster_assets.items():

        image = ee.Image(asset_id)

        bands = vegetation_bands_by_year[year]

        vegetation = (
            image
            .select(bands)
            .reduce(ee.Reducer.sum())
            .rename("vegetation")
        )

        vegetation = vegetation.set("year", year)

        images.append(vegetation)

    return ee.ImageCollection(images)