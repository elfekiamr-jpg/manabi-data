"""
02_join_idf_and_finalize.py

Stage 2 of the Manabi "enriched catchment" pipeline.

Takes:
  - your original MERIT-Basins catchment geometries (same file you
    uploaded to Earth Engine in stage 1)
  - the CN CSV that stage 1's export produced (download it from the
    Google Drive folder once the EE task finishes)
  - a local IDF raster/param file (BURGER or PXR-4 — see NOTE below)

and produces one enriched catchment table: geometry + upstream area
(already in your MERIT-Basins attributes) + CN_dry/avg/wet + IDF
params. This is the file your Flask API reads at runtime — no
external API calls per request.

NOTE on IDF source
-------------------
BURGER (2025, CC BY 4.0) and PXR-4 (2019, open, Zenodo) are both
research outputs, not indexed in Earth Engine, so grab them
directly:
  - BURGER: search "BURGER Bottom-Up Regionalized Global Extreme
    Rainfall" — Newcastle University ePrints / associated repository.
  - PXR-4 (fallback, coarser but simpler — 4 params per cell,
    algebraic IDF formula): https://zenodo.org/record/2616438

Download as GeoTIFF (or NetCDF — adjust the loader below if so) and
point IDF_RASTER_PATH at it. If it ships as multiple single-band
files (one per parameter), loop this over each and merge — see
comment near add_idf_stats().

Install:
    pip install geopandas rasterstats pandas rasterio
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd
from rasterstats import zonal_stats

# ---------------------------------------------------------------- #
# CONFIG — edit these
# ---------------------------------------------------------------- #

# Original catchment file (same one uploaded to EE in stage 1)
CATCHMENTS_PATH = "path/to/egypt_catchments.shp"
CATCHMENT_ID_FIELD = "COMID"

# CSV downloaded from Google Drive after the stage-1 export finished
CN_CSV_PATH = "path/to/gcn250_egypt.csv"

# Local IDF raster (BURGER or PXR-4 GeoTIFF — one band per parameter,
# or point this at a directory and adjust the loop below if the
# dataset ships as separate files per parameter)
IDF_RASTER_PATH = "path/to/idf_params.tif"
IDF_BAND_NAMES = ["idf_param_1", "idf_param_2", "idf_param_3", "idf_param_4"]

OUTPUT_PATH = "path/to/enriched_catchments_egypt.parquet"


# ---------------------------------------------------------------- #

def add_curve_numbers(catchments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    cn = pd.read_csv(CN_CSV_PATH)
    merged = catchments.merge(cn, on=CATCHMENT_ID_FIELD, how="left")

    missing = merged["CN_avg"].isna().sum()
    if missing:
        print(f"WARNING: {missing} catchments have no CN match — "
              f"check that {CATCHMENT_ID_FIELD} values line up between "
              f"the shapefile and the EE export.")
    return merged


def add_idf_stats(catchments: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # zonal_stats handles the reprojection/rasterization itself as
    # long as the vector and raster CRS are both defined; it's
    # local computation so fine for catchment-count in the low
    # hundreds of thousands. For a full global run in one go,
    # switch this to a tiled/chunked loop over catchments.
    stats = zonal_stats(
        catchments,
        IDF_RASTER_PATH,
        stats="mean",
        band=list(range(1, len(IDF_BAND_NAMES) + 1)),
        all_touched=True,
        geojson_out=False,
    )
    stats_df = pd.DataFrame(stats)

    # rasterstats names multi-band mean columns like "mean_1","mean_2"...
    rename_map = {f"mean_{i+1}": name for i, name in enumerate(IDF_BAND_NAMES)}
    stats_df = stats_df.rename(columns=rename_map)

    for col in IDF_BAND_NAMES:
        catchments[col] = stats_df[col].values

    return catchments


def main():
    print("Loading catchments...")
    catchments = gpd.read_file(CATCHMENTS_PATH)

    print("Joining curve numbers...")
    catchments = add_curve_numbers(catchments)

    print("Joining IDF parameters...")
    catchments = add_idf_stats(catchments)

    out_path = Path(OUTPUT_PATH)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    catchments.to_parquet(out_path)

    print(f"Done. Enriched catchment table written to {out_path}")
    print(f"  {len(catchments)} catchments, columns: {list(catchments.columns)}")


if __name__ == "__main__":
    main()
