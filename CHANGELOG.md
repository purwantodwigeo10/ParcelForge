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
- Add live 0–100 percent progress and safe cancellation.
- Validate field creation and every attribute update before saving output.
- Protect existing GeoPackage, Shapefile, and companion destinations.
- Support GeoPackage and Shapefile output.
- Include synthetic DXF sample data and usage documentation.
