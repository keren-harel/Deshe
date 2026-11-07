# -*- coding: utf-8 -*-
"""
FuelBreakStudy.pyt
ArcGIS Pro Python toolbox for the Fuel Break Vegetation Analysis workflow.

Expected project modules in the same folder (or on Python's sys.path):
    config.py
    preprocessing.py
    analysis.py
    gee_utils.py

The toolbox uses the current analysis outputs:
    change
    thinning
    vegetation_growth_metrics
        - recovery_score
        - growth_trend
        - consistency

The Study Area parameter expects a Google Earth Engine FeatureCollection asset ID.
"""

import os
import re
import sys
import tempfile
import zipfile
from io import BytesIO
from urllib.request import urlopen

import arcpy


class Toolbox(object):
    def __init__(self):
        self.label = "Fuel Break Study"
        self.alias = "fuelbreakstudy"
        self.tools = [FuelBreakAnalysis]


class FuelBreakAnalysis(object):
    def __init__(self):
        self.label = "Fuel Break Vegetation Analysis"
        self.description = (
            "Detects vegetation thinning between two selected years and "
            "calculates post-treatment tree-cover recovery metrics."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        # Study area is an Earth Engine asset ID, as expected by gee_utils.load_study_area().
        study_area = arcpy.Parameter(
            displayName="Study Area",
            name="study_area",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        study_area.filter.list = ["Polygon"]

        before_year = arcpy.Parameter(
            displayName="Before Year",
            name="before_year",
            datatype="GPLong",
            parameterType="Required",
            direction="Input"
        )

        after_year = arcpy.Parameter(
            displayName="After / Treatment Year",
            name="after_year",
            datatype="GPLong",
            parameterType="Required",
            direction="Input"
        )

        output_gdb = arcpy.Parameter(
            displayName="Output Geodatabase",
            name="output_gdb",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
        )

        # Populate defaults from config when it is importable.
        try:
            import config

            available_years = sorted(
                int(year) for year in config.RASTERS.keys()
            )
            before_year.filter.type = "ValueList"
            before_year.filter.list = available_years
            after_year.filter.type = "ValueList"
            after_year.filter.list = available_years

            # Use the configured before/after years when available.
            configured_before = getattr(config, "BEFORE_YEAR", None)
            configured_after = getattr(config, "AFTER_YEAR", None)
            if configured_before in available_years:
                before_year.value = configured_before
            elif available_years:
                before_year.value = available_years[0]

            if configured_after in available_years:
                after_year.value = configured_after
            elif len(available_years) > 1:
                after_year.value = available_years[1]

        except Exception:
            # updateMessages() provides a clearer diagnostic if config is unavailable.
            pass

        try:
            project = arcpy.mp.ArcGISProject("CURRENT")
            output_gdb.value = project.defaultGeodatabase
        except Exception:
            pass

        return [study_area, before_year, after_year, output_gdb]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        # Keep the default output workspace synchronized with the current project.
        if not parameters[3].altered:
            try:
                project = arcpy.mp.ArcGISProject("CURRENT")
                parameters[3].value = project.defaultGeodatabase
            except Exception:
                pass
        return

    def updateMessages(self, parameters):
        # Validate year selection against the configured annual raster collection.
        try:
            import config
            years = sorted(int(year) for year in config.RASTERS.keys())

            for index, label in ((1, "Before Year"), (2, "After Year")):
                value = parameters[index].value
                if value is not None and int(value) not in years:
                    parameters[index].setErrorMessage(
                        "{} is not available in config.RASTERS.".format(label)
                    )

            if parameters[1].value and parameters[2].value:
                if int(parameters[2].value) <= int(parameters[1].value):
                    parameters[2].setErrorMessage(
                        "After Year must be later than Before Year."
                    )
        except Exception as exc:
            parameters[0].setWarningMessage(
                "Could not validate configured years: {}".format(exc)
            )

        if parameters[0].value:
            asset_id = str(parameters[0].value).strip()
            if not asset_id.startswith(("projects/", "users/")):
                parameters[0].setWarningMessage(
                    "Enter a Google Earth Engine asset ID, e.g. "
                    "projects/your-project/assets/study_area."
                )

        return

    def execute(self, parameters, messages):
        study_area_layer = parameters[0].valueAsText
        before_year = int(parameters[1].value)
        after_year = int(parameters[2].value)
        output_gdb = parameters[3].valueAsText

        if not arcpy.Exists(output_gdb):
            raise arcpy.ExecuteError(
                "The output geodatabase does not exist: {}".format(output_gdb)
            )

        # Import project modules at execution time so ArcGIS Pro reports
        # environment/module errors as geoprocessing messages.
        try:
            import ee
            import config
            import preprocessing
            import analysis
            import gee_utils
        except Exception as exc:
            arcpy.AddError(
                "Could not import the project modules or Earth Engine package. "
                "Check that ArcGIS Pro's Python environment contains the required "
                "packages and that the project folder is on sys.path. Details: {}"
                .format(exc)
            )
            arcpy.AddError("Python executable: {}".format(sys.executable))
            arcpy.AddError("Python version: {}".format(sys.version))
            arcpy.AddError("sys.path: {}".format(sys.path))
            raise

        arcpy.AddMessage("Initializing Google Earth Engine...")
        gee_utils.initialize_gee(config.PROJECT_ID)

        arcpy.AddMessage("Converting Study Area to Earth Engine geometry...")

        study_area = arcgis_polygon_to_ee(
            study_area_layer,
            ee
        )

        buffer_distance = getattr(config, "BUFFER_DISTANCE", 200)
        buffer = preprocessing.create_buffer(study_area, buffer_distance)

        before_asset = config.RASTERS[before_year]
        after_asset = config.RASTERS[after_year]

        arcpy.AddMessage(
            "Loading annual rasters: {} and {}...".format(before_year, after_year)
        )
        raster_before_original = gee_utils.load_raster(before_asset)
        raster_after_original = gee_utils.load_raster(after_asset)

        use_mega_pixels = bool(getattr(config, "USE_MEGA_PIXELS", False))
        if use_mega_pixels:
            mega_pixel_size = getattr(config, "MEGA_PIXEL_SIZE", 30)
            arcpy.AddMessage(
                "Aggregating rasters to {} m mega-pixels...".format(mega_pixel_size)
            )
            raster_before = preprocessing.aggregate_to_mega_pixels(
                raster_before_original, mega_pixel_size
            )
            raster_after = preprocessing.aggregate_to_mega_pixels(
                raster_after_original, mega_pixel_size
            )
        else:
            raster_before = raster_before_original
            raster_after = raster_after_original

        raster_before = preprocessing.clip_to_buffer(raster_before, buffer)
        raster_after = preprocessing.clip_to_buffer(raster_after, buffer)

        # Detect thinning using the vegetation-band configuration already used
        # by the current analysis module.
        bands_before = getattr(config, "VEGETATION_BANDS_BEFORE", None)
        bands_after = getattr(config, "VEGETATION_BANDS_AFTER", None)
        if bands_before is None or bands_after is None:
            raise arcpy.ExecuteError(
                "config.py must define VEGETATION_BANDS_BEFORE and "
                "VEGETATION_BANDS_AFTER."
            )

        arcpy.AddMessage("Calculating vegetation change and thinning mask...")
        change = analysis.calculate_vegetation_change(
            raster_before,
            raster_after,
            bands_before,
            bands_after
        )

        threshold = getattr(config, "CHANGE_THRESHOLD", 15)
        thinning = analysis.identify_thinning(change, threshold)

        # Load the annual time series. The loader is expected to select the
        # year-specific tree-cover band and set the image property 'year'.
        arcpy.AddMessage("Loading annual tree-cover time series...")
        annual_images = gee_utils.load_annual_images(
        config.RASTERS,
        config.VEGETATION_TREE_BAND_BY_YEAR
        )

        arcpy.AddMessage("Checking annual image collection...")

        arcpy.AddMessage(
            "Image count: {}".format(
                annual_images.size().getInfo()
            )
        )

        arcpy.AddMessage(
            "Years: {}".format(
                annual_images.aggregate_array("year").getInfo()
            )
        )

        arcpy.AddMessage(
            "First image bands: {}".format(
                ee.Image(annual_images.first()).bandNames().getInfo()
            )
        )

        # Recovery baseline images must contain the tree-cover band only.
        tree_band_map = config.VEGETATION_TREE_BAND_BY_YEAR

        if before_year not in tree_band_map or after_year not in tree_band_map:
            raise arcpy.ExecuteError(
                "VEGETATION_TREE_BAND_BY_YEAR must contain entries for both selected years."
            )

        tree_pre = (
            raster_before
            .select(tree_band_map[before_year])
            .rename("tree_pre")
        )

        tree_t0 = (
            raster_after
            .select(tree_band_map[after_year])
            .rename("tree_t0")
        )

        # Apply the same clipping extent to the annual collection. If mega-pixels
        # are enabled, aggregate each annual image to the same analysis scale.
        def prepare_annual_image(image):
            image = ee.Image(image)
            if use_mega_pixels:
                image = preprocessing.aggregate_to_mega_pixels(
                    image, getattr(config, "MEGA_PIXEL_SIZE", 30)
                )
            return preprocessing.clip_to_buffer(image, buffer)

        annual_images = annual_images.map(prepare_annual_image)

        arcpy.AddMessage("Calculating recovery metrics...")
        metrics_function = analysis.calculate_vegetation_recovery_metrics

        # The current analysis.py version accepts four arguments. Filter the
        # annual collection here so growth and consistency use only years from
        # the selected treatment / T0 year onward.
        annual_images = annual_images.filter(
            ee.Filter.gte("year", after_year)
        ).sort("year")

        vegetation_growth_metrics = metrics_function(
            annual_images,
            thinning,
            tree_pre,
            tree_t0,
        
        )

        results = {
            "change": change,
            "thinning": thinning,
            "vegetation_growth_metrics": vegetation_growth_metrics
        }

        scale = getattr(config, "EXPORT_SCALE", 10)
        arcpy.AddMessage("Downloading results and writing them to the output geodatabase...")

        _export_results_to_gdb(
            ee_module=ee,
            results=results,
            region=buffer,
            output_gdb=output_gdb,
            scale=scale,
            arcpy_module=arcpy
        )

        arcpy.AddMessage("Fuel Break Vegetation Analysis completed successfully.")
        return

def arcgis_polygon_to_ee(layer, ee):
    """
    Convert an ArcGIS Pro polygon layer to
    an Earth Engine FeatureCollection.
    """

    import json
    import tempfile
    import os

    # Check geometry type
    desc = arcpy.Describe(layer)

    if desc.shapeType != "Polygon":
        raise arcpy.ExecuteError(
            "Study Area must be a polygon layer."
        )

    # Export polygons to GeoJSON in WGS84
    with tempfile.TemporaryDirectory() as temp_dir:

        geojson_path = os.path.join(
            temp_dir,
            "study_area.geojson"
        )

        arcpy.conversion.FeaturesToJSON(
            in_features=layer,
            out_json_file=geojson_path,
            geoJSON="GEOJSON",
            outputToWGS84="WGS84"
        )

        with open(geojson_path, "r", encoding="utf-8") as f:
            geojson = json.load(f)

    # Convert GeoJSON features to EE features
    ee_features = []

    for feature in geojson["features"]:

        geometry = ee.Geometry(feature["geometry"])

        ee_features.append(
            ee.Feature(geometry)
        )

    return ee.FeatureCollection(ee_features)

def _safe_name(name):
    """Return a geodatabase-safe feature/raster dataset name."""
    name = re.sub(r"[^A-Za-z0-9_]", "_", str(name))
    if not name or not name[0].isalpha():
        name = "out_" + name
    return name[:fifty_chars()]


def fifty_chars():
    # File geodatabase raster names are safely kept below the usual name limit.
    return 50


def _download_ee_image(image, region, scale, destination):
    """Download an Earth Engine image as GeoTIFF to destination."""
    try:
        region_geometry = region.geometry()
    except Exception:
        # create_buffer() may return an ee.Geometry directly rather than a
        # FeatureCollection / Feature.
        region_geometry = region

    params = {
        "scale": scale,
        "region": region_geometry.getInfo(),
        "format": "GEO_TIFF"
    }
    url = image.unmask(-9999).getDownloadURL(params)
    with urlopen(url, timeout=300) as response:
        payload = response.read()

    # Earth Engine may return a ZIP archive for multi-band downloads.
    if zipfile.is_zipfile(BytesIO(payload)):
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            tif_names = [
                name for name in archive.namelist()
                if name.lower().endswith((".tif", ".tiff"))
            ]
            if not tif_names:
                raise RuntimeError("Earth Engine download ZIP contains no GeoTIFF.")
            with archive.open(tif_names[0]) as src, open(destination, "wb") as dst:
                dst.write(src.read())
    else:
        with open(destination, "wb") as dst:
            dst.write(payload)


def _export_results_to_gdb(
        ee_module,
        results,
        region,
        output_gdb,
        scale,
        arcpy_module
):
    """Export analysis results to the selected file geodatabase."""

    output_images = {
        "vegetation_change": results["change"],
        "thinning": results["thinning"],
        "vegetation_growth_metrics": results["vegetation_growth_metrics"]
    }

    # Export each recovery metric separately
    metrics = results["vegetation_growth_metrics"]

    metric_bands = [
        "recovery_score",
        "growth_trend",
        "consistency"
    ]

    for band in metric_bands:
        output_images[band] = metrics.select(band)

    # Get current ArcGIS Pro map
    project = arcpy_module.mp.ArcGISProject("CURRENT")
    maps = project.listMaps()
    target_map = maps[0] if maps else None

    with tempfile.TemporaryDirectory(
            prefix="fuel_break_study_"
    ) as temp_dir:

        for output_name, image in output_images.items():

            safe_output_name = _safe_name(output_name)

            tif_path = os.path.join(
                temp_dir,
                safe_output_name + ".tif"
            )

            gdb_path = os.path.join(
                output_gdb,
                safe_output_name
            )

            arcpy_module.AddMessage(
                "Starting export: {}".format(output_name)
            )

            # Check band names
            band_names = image.bandNames().getInfo()

            arcpy_module.AddMessage(
                "Bands: {}".format(band_names)
            )

            # Download image
            arcpy_module.AddMessage(
                "Downloading: {}".format(output_name)
            )

            _download_ee_image(
                image,
                region,
                scale,
                tif_path
            )

            arcpy_module.AddMessage(
                "Download completed: {}".format(output_name)
            )

            # Replace existing raster
            if arcpy_module.Exists(gdb_path):
                arcpy_module.management.Delete(gdb_path)

            # Copy GeoTIFF to GDB
            arcpy_module.management.CopyRaster(
                in_raster=tif_path,
                out_rasterdataset=gdb_path,
                pixel_type="32_BIT_FLOAT",
                nodata_value="-9999"
            )

            # Add raster to current map
            if target_map is not None:
                target_map.addDataFromPath(gdb_path)

            arcpy_module.AddMessage(
                "Created: {}".format(gdb_path)
            )