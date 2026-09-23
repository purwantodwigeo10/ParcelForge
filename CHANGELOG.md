# Changelog

## 26.1.0

- Build polygons from clean, closed DXF boundary linework.
- Map DXF text from as many as ten CAD layers into user-defined attributes.
- Require the user to assign the actual DXF CRS without changing coordinates.
- Reject ambiguous text on polygon boundaries or overlapping polygons.
- Report labels read, mapped, outside polygons, duplicated, and combined.
- Stop when a selected text layer produces no mapped value.
- Preserve unique multiple values using ` | ` instead of silently dropping
  data.
- Add cancellable QGIS processing with visible progress and re-entry guards.
- Validate field creation and every attribute update before saving output.
- Protect existing GeoPackage, Shapefile, and companion destinations.
- Use the QGIS V3 vector writer and GDAL/OGR supplied with QGIS.
- Use scoped Qt enums and compatibility helpers required by current checks.
- Harden bounded HTTPS License Hub requests and activation-response parsing.
- Keep trial runs offline until an activation code or active license exists.
- Include synthetic DXF sample data, complete documentation, and GPL license.
