# Revision notes — ParcelForge 26.1.0

The version remains `26.1.0` at the author's request.

## Functional corrections

- Enforce the maximum of ten mappings in both the dialog and processing core.
- Ignore blank DXF text and stop when a selected text layer maps no value.
- Require labels to be strictly inside one polygon. Labels on an edge, inside
  overlapping polygons, or touching multiple polygons are rejected instead of
  being assigned arbitrarily.
- Count and expose unmapped outside labels, ignored duplicates, and polygons
  with multiple unique values.
- Validate temporary fields, output fields, editing, each attribute change, and
  the final writer result.
- Use unlimited GeoPackage text fields and the Shapefile 254-character limit.
- Recheck destination safety immediately before writing.
- Segmentize curved boundaries before polygonization and retain the explicit
  user-assigned source CRS.
- Add progress feedback and cancellation forwarded to the QGIS polygonize
  algorithm and checked during text mapping.

## Compatibility and security corrections

- Replace the remaining flat QGIS geometry enum with a scoped-enum
  compatibility helper.
- Keep scoped Qt enums, `exec()`, Qt-compatible QAction imports, and explicit
  Qt5/Qt6 field types while claiming QGIS 3.x only.
- Validate inputs and destination safety before any activation-network check.
- Try all supported activation payload field names before accepting an
  inactive result.
- Treat response keys case-insensitively and let explicit denial states take
  priority within every response.
- Avoid unnecessary License Hub traffic for unused trials.
- Use QGIS' network manager, strict HTTPS host allowlisting, manual redirect
  handling, a timeout, and a one-megabyte response limit.
- Store local state atomically and apply restrictive permissions where the
  operating system supports them.

## Validation scope

The final build is checked with Python compilation, focused linting, offline
unit/regression tests, standalone Qt5/Qt6 enum inspection, sample-DXF parsing,
archive safety checks, metadata checks, and security-oriented static scans.

A complete QGIS/GDAL end-to-end run and live License Hub activation cannot be
emulated outside an installed QGIS environment. Before publication, run the
manual test matrix in `PUBLISHING_GUIDE_ID.md` on the target QGIS installation.
The metadata retains QGIS 3.22–3.99 compatibility and does not claim QGIS 4.
