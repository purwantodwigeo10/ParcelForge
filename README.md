# ParcelForge

ParcelForge is a QGIS plugin that builds parcel polygons from clean DXF
boundary lines and transfers DXF text into as many as ten user-defined polygon
attributes. The QGIS edition accepts DXF only; DWG is deliberately not shown
or accepted.

## Requirements

- QGIS 3.22 or later in the QGIS 3 series (`qgisMaximumVersion=3.99`).
- Windows, Linux, or macOS.
- GDAL/OGR DXF support supplied by the QGIS installation.
- Closed, topologically connected boundary linework without critical gaps,
  duplicates, overlaps, overshoots, undershoots, or unwanted dangling lines.
- Text placed clearly inside its intended polygon and separated into CAD
  information layers.
- The actual CRS of the DXF coordinates must be known.

ParcelForge assigns the CRS selected by the user. It does not transform or
reproject the raw DXF coordinates. Output may be GeoPackage (recommended) or
Shapefile.

## Installation

1. In QGIS, open **Plugins > Manage and Install Plugins**.
2. Select **Install from ZIP**.
3. Select the ParcelForge release ZIP without extracting it.
4. Confirm the security warning only when the ZIP came from this repository or
   the official QGIS Plugins Directory.
5. Enable **ParcelForge** and open it from **Vector > ParcelForge** or its
   toolbar button.

## Workflow

1. Select an input `.dxf` file.
2. Select the CAD layer containing the parcel boundary lines.
3. Select the actual CRS of the DXF coordinates. This assigns a CRS only.
4. Choose 1–10 attribute mappings. For each mapping, enter an output field name
   and select the CAD text layer that contains the values.
5. Choose a new `.gpkg` or `.shp` output filename.
6. Run ParcelForge. The progress bar and **Cancel** button remain available
   while QGIS processing is running.

ParcelForge never overwrites an existing destination. For Shapefile output,
all companion files with the same basename are protected too.

## Text mapping rules

- A label must be strictly inside one polygon.
- A label on a polygon edge or touching multiple polygons stops processing
  with a clear ambiguity message instead of being assigned arbitrarily.
- Labels outside all polygons are skipped and reported in the completion
  summary.
- If an entire selected text layer maps to no polygon, processing stops so an
  empty field is not silently produced.
- Repeated identical text inside the same polygon is stored once.
- Multiple different values in one polygon are retained in deterministic read
  order and joined with ` | `; the completion summary reports this condition.
- Shapefile field names are sanitized and limited to 10 characters. A numeric
  suffix is added when names would collide. GeoPackage permits longer names.
- Shapefile text values are limited to 254 characters. Prefer GeoPackage when
  long text must be retained.

## Bundled functional check

`sample_data/parcels.dxf` contains two closed rectangles on `BOUNDARY` and two
labels on `OWNER`.

1. Select `BOUNDARY` as the boundary layer.
2. Select a projected CRS for this synthetic planar test only. Its coordinates
   are arbitrary and are not surveyed data.
3. Configure one mapping: output field `OWNER`, source text layer `OWNER`.
4. Save to a new GeoPackage.
5. Expect two polygons with `OWNER_A` and `OWNER_B`.

## Activation

- Product code: `PARFOR`
- Fixed code: `EIN`
- Trial: 2 successful processing runs

Trial use is recorded only after a successful output is created.

## Source, help, and support

- Help: <https://aktivasi.ruangspasial.my.id/help/parcelforge-qgis>
- Source: <https://github.com/purwantodwigeo10/ParcelForge>
- Issues: <https://github.com/purwantodwigeo10/ParcelForge/issues>

Copyright (C) 2026 Dwi Purwanto / Ruang Spasial. Licensed under
GPL-3.0-or-later; see `LICENSE`.
