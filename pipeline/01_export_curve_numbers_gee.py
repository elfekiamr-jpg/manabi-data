"""
01_export_curve_numbers_gee.py

Stage 1 of the Manabi "enriched catchment" pipeline.

Computes average GCN250 curve number (dry / average / wet antecedent
condition) for every MERIT-Basins catchment, using Google Earth Engine
server-side (avoids downloading a 250m global raster locally).

WHY THIS SHAPE
--------------
For a global run, MERIT-Basins is well over a million catchments.
Building an ee.FeatureCollection() client-side from a Python list
of features will time out / hit request-size limits at that scale.
The correct pattern is:

  1. Upload your catchment polygons ONCE as an Earth Engine table
     asset (via the `earthengine` CLI — see SETUP below).
  2. Run reduceRegions() entirely server-side against that asset.
  3. Export the result table to Drive/GCS as CSV (async job — GEE
     emails you / shows it in the Tasks tab when done, can take
     minutes to hours depending on region size).
  4. Stage 2 script joins that CSV back onto your local catchment
     geometries.

For a first pass, run this per-country or per-megabasin (matching
how you're already sharding eg-watersheds / ksa-watersheds) rather
than attempting the whole globe in one export — much easier to
debug and re-run on failure.

SETUP (one-time)
-----------------
    pip install earthengine-api geopandas

    # Authenticate (opens browser once, then cached)
    earthengine authenticate

    # Upload your catchment layer as an EE table asset.
    # Source can be a Shapefile, GeoPackage layer exported to
    # Shapefile, or GeoJSON. Must contain a unique catchment ID
    # field (MERIT-Basins convention: COMID).
    earthengine upload table \\
        --asset_id=users/YOUR_EE_USERNAME/manabi_catchments_egypt \\
        path/to/egypt_catchments.shp

Then edit CATCHMENT_ASSET_ID below and run this script normally
with `python 01_export_curve_numbers_gee.py`.

License note: GCN250 is CC BY 4.0 (Jaafar, Ahmad & El Beyrouthy,
2019, https://doi.org/10.1038/s41597-019-0155-x) — free for
commercial use, attribution only, no share-alike. Cite it in your
about/attribution page.
"""

import ee

# ---------------------------------------------------------------- #
# CONFIG — edit these
# ---------------------------------------------------------------- #

# EE table asset you uploaded via `earthengine upload table` (see
# SETUP above). One region/country/megabasin at a time is fine.
CATCHMENT_ASSET_ID = "users/YOUR_EE_USERNAME/manabi_catchments_egypt"

# Field in your catchment table that uniquely identifies each
# catchment. MERIT-Basins' native field name is COMID — change if
# your delineator library renames it.
CATCHMENT_ID_FIELD = "COMID"

# Where the result CSV lands (a Google Drive folder in your account,
# created automatically if it doesn't exist).
DRIVE_FOLDER = "manabi_gcn250_exports"
EXPORT_DESCRIPTION = "gcn250_egypt"  # rename per region/run

# GCN250 Earth Engine asset IDs (Jaafar et al. 2019, CC BY 4.0)
GCN250_DRY = "users/jaafarhadi/GCN250/GCN250Dry"
GCN250_AVG = "users/jaafarhadi/GCN250/GCN250Average"
GCN250_WET = "users/jaafarhadi/GCN250/GCN250Wet"


# ---------------------------------------------------------------- #

def main():
    ee.Initialize()

    catchments = ee.FeatureCollection(CATCHMENT_ASSET_ID)

    # Stack the three CN images into one multi-band image so a
    # single reduceRegions() call gets all three conditions at once.
    cn_stack = (
        ee.Image(GCN250_DRY).rename("CN_dry")
        .addBands(ee.Image(GCN250_AVG).rename("CN_avg"))
        .addBands(ee.Image(GCN250_WET).rename("CN_wet"))
    )

    # Mean CN per catchment polygon. scale=250 matches native
    # GCN250 resolution — don't set it finer, it just wastes compute.
    stats = cn_stack.reduceRegions(
        collection=catchments,
        reducer=ee.Reducer.mean(),
        scale=250,
        tileScale=4,  # raise if you hit "computation timed out" on big catchments
    )

    # Keep only the ID + the three CN columns in the export —
    # geometry travels separately via your local catchment file,
    # no need to re-export it from EE.
    stats = stats.select(
        propertySelectors=[CATCHMENT_ID_FIELD, "CN_dry", "CN_avg", "CN_wet"],
        retainGeometry=False,
    )

    task = ee.batch.Export.table.toDrive(
        collection=stats,
        description=EXPORT_DESCRIPTION,
        folder=DRIVE_FOLDER,
        fileFormat="CSV",
    )
    task.start()

    print(f"Export task '{EXPORT_DESCRIPTION}' started.")
    print("Check progress at https://code.earthengine.google.com/tasks")
    print(f"Result will appear in Google Drive folder: {DRIVE_FOLDER}/{EXPORT_DESCRIPTION}.csv")


if __name__ == "__main__":
    main()
