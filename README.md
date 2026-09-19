# ParcelForge

ParcelForge builds polygons from clean DXF boundary lines and transfers DXF
text into up to ten user-defined polygon attributes. The QGIS edition accepts
DXF only; DWG is deliberately not shown or accepted.

## Requirements

- QGIS 3.22 through 3.99 on Windows, Linux, or macOS.
- GDAL/OGR DXF support included with the QGIS installation.
- Closed, topologically connected boundary linework without gaps, duplicates,
  overlaps, overshoots, undershoots, or unwanted dangling lines.
- Text located inside its intended polygon and separated by information layer.

Output may be GeoPackage (recommended) or Shapefile.

## Installation and quick test

1. Install the release ZIP from QGIS **Plugins > Manage and Install Plugins >
   Install from ZIP** and enable **ParcelForge**.
2. Open it from **Vector > ParcelForge** or its toolbar button.
3. Select `sample_data/parcels.dxf` and inspect its available layers.
4. Select the boundary layer, configure an `OWNER` output field from the OWNER
   text layer, and choose a new GeoPackage output.
5. Run ParcelForge and verify that two polygons and their text attributes exist.

The bundled DXF is synthetic and intended only as a small functional check.

## Activation and privacy

- Product code: `PARFOR`
- Fixed code: `EIN`
- Trial: 2 successful processing runs

Trial use is recorded only after successful output creation. Activation and
active-license checks use QGIS' network manager and HTTPS at
`aktivasi.ruangspasial.my.id`. Only the product identity, activation code, and a
pseudonymous Device ID are sent. CAD/GIS content and paths are never
transmitted. Local state is stored in the current user's application-data
directory.

## Source, help, and support

- Help: <https://aktivasi.ruangspasial.my.id/help/parcelforge-qgis>
- Source: <https://github.com/purwantodwigeo10/parcelforge-qgis>
- Issues: <https://github.com/purwantodwigeo10/parcelforge-qgis/issues>

Copyright (C) 2026 Dwi Purwanto / Ruang Spasial. Licensed under
GPL-3.0-or-later; see `LICENSE`.
