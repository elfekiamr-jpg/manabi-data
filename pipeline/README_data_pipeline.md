# Manabi global — enriched catchment pipeline

Two scripts, run once per region (or globally once you're ready), to
build the data your runtime API reads. No external API calls happen
at request time — everything's precomputed and joined onto your
existing MERIT-Basins catchments.

## Run order

1. **`01_export_curve_numbers_gee.py`**
   Uploads nothing itself — you upload your catchment shapefile to
   Earth Engine once via the `earthengine` CLI (instructions in the
   script's docstring), then this script kicks off a server-side
   zonal-stats job (GCN250 curve numbers × your catchments) and
   exports the result CSV to Google Drive. Async — check
   https://code.earthengine.google.com/tasks for completion.

2. **`02_join_idf_and_finalize.py`**
   Downloads the CSV from Drive, joins it plus a local IDF raster
   (BURGER, or PXR-4 as fallback — links in the script) onto your
   original catchment geometries, and writes one Parquet file:
   `enriched_catchments_<region>.parquet` — geometry, upstream area,
   CN_dry/avg/wet, IDF params, ready for your Flask API to load
   directly.

Run per-region first (Egypt, KSA) to validate the join logic and
catch ID-mismatch issues cheaply, then scale to full-globe exports.

## Runtime use (sketch, for when you build the API endpoint)

```
pour point → snap to catchment → traverse upstream (existing logic)
  → basin = union of included catchments
  → area = sum(upstream_area)
  → CN or C = area-weighted mean of CN_avg (or dry/wet per user toggle)
  → Tc = Kirpich(flow path length, slope)  # from your DEM, no dataset needed
  → I = evaluate IDF params at basin outlet, duration = Tc, for chosen return period
  → basin ≤ ~80 ha → Q = C × I × A        (Rational Method)
     basin  > ~80 ha → NRCS-CN + unit hydrograph, using CN directly
```

## Licensing reminder

- GCN250: CC BY 4.0 — attribute Jaafar, Ahmad & El Beyrouthy (2019),
  no other restriction.
- MERIT-Basins: dual CC-BY-NC / ODbL — you're using ODbL, so publish
  the resulting enriched catchment table publicly (a public repo or
  static file, same pattern as eg-watersheds) to stay compliant.
  Your API, UI, and paid features stay proprietary.
- BURGER / PXR-4: CC BY 4.0 — attribute the source paper.
