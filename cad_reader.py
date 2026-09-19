# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from osgeo import ogr

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsProject,
    QgsSpatialIndex,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)

import processing


LAYER_FIELD_CANDIDATES = [
    "Layer",
    "layer",
    "LAYER",
]

TEXT_FIELD_CANDIDATES = [
    "Text",
    "TxtValue",
    "TextString",
    "String",
    "Label",
    "text",
    "TEXT",
    "MTEXT",
    "Contents",
    "Content",
]


def _geometry_name(ogr_geometry):
    """
    Return a normalized OGR geometry name without relying on wkbFlatten,
    which is not exposed by every GDAL/OGR Python build.
    """
    if ogr_geometry is None:
        return ""

    try:
        name = ogr_geometry.GetGeometryName()
        if name:
            return str(name).strip().upper()
    except (AttributeError, RuntimeError):
        name = ""

    try:
        geometry_type = ogr_geometry.GetGeometryType()

        if hasattr(ogr, "GT_Flatten"):
            geometry_type = ogr.GT_Flatten(geometry_type)

        return str(
            ogr.GeometryTypeToName(geometry_type)
        ).strip().upper()

    except Exception:
        return ""


def _is_line_geometry(ogr_geometry):
    """
    Support standard and curved CAD line geometries.
    """
    geometry_name = _geometry_name(ogr_geometry)

    return geometry_name in {
        "LINESTRING",
        "MULTILINESTRING",
        "CIRCULARSTRING",
        "COMPOUNDCURVE",
        "MULTICURVE",
        "LINEARRING",
    }


def _field_name(layer_definition, candidates):
    names = [
        layer_definition.GetFieldDefn(index).GetName()
        for index in range(
            layer_definition.GetFieldCount()
        )
    ]

    lookup = {
        name.lower(): name
        for name in names
    }

    for candidate in candidates:
        found = lookup.get(
            candidate.lower()
        )
        if found:
            return found

    return None


def _qgs_geometry(ogr_geometry):
    if ogr_geometry is None:
        return None

    geometry = QgsGeometry()
    geometry.fromWkb(
        bytes(ogr_geometry.ExportToWkb())
    )
    return geometry


def _open_dataset(dwg_path):
    if not str(dwg_path).lower().endswith(".dxf"):
        raise RuntimeError(
            "ParcelForge QGIS accepts DXF files only."
        )

    if not os.path.isfile(dwg_path):
        raise RuntimeError(
            "The selected DXF file does not exist."
        )

    dataset = ogr.Open(
        dwg_path,
        0
    )

    if dataset is None:
        raise RuntimeError(
            "QGIS/GDAL could not open the selected DXF file. "
            "Confirm that the DXF file is valid and readable."
        )

    return dataset


def scan_layers(dwg_path):
    dataset = _open_dataset(dwg_path)
    boundary_layers = set()
    text_layers = set()

    for layer_index in range(
            dataset.GetLayerCount()):
        layer = dataset.GetLayerByIndex(
            layer_index
        )
        definition = layer.GetLayerDefn()
        layer_field = _field_name(
            definition,
            LAYER_FIELD_CANDIDATES
        )
        text_field = _field_name(
            definition,
            TEXT_FIELD_CANDIDATES
        )

        layer.ResetReading()

        for feature in layer:
            cad_layer = (
                str(feature.GetField(layer_field)).strip()
                if layer_field
                and feature.GetField(layer_field) is not None
                else layer.GetName()
            )

            geometry = feature.GetGeometryRef()

            if (
                    geometry is not None
                    and _is_line_geometry(geometry)):
                boundary_layers.add(
                    cad_layer
                )

            if (
                    text_field
                    and feature.GetField(text_field)
                    not in [None, ""]):
                text_layers.add(
                    cad_layer
                )

        layer.ResetReading()

    return (
        sorted(
            boundary_layers,
            key=str.upper
        ),
        sorted(
            text_layers,
            key=str.upper
        ),
    )


def _collect_boundary_geometries(
    dataset,
    selected_layer
):
    geometries = []

    for layer_index in range(
            dataset.GetLayerCount()):
        layer = dataset.GetLayerByIndex(
            layer_index
        )
        definition = layer.GetLayerDefn()
        layer_field = _field_name(
            definition,
            LAYER_FIELD_CANDIDATES
        )
        layer.ResetReading()

        for feature in layer:
            cad_layer = (
                str(feature.GetField(layer_field)).strip()
                if layer_field
                and feature.GetField(layer_field) is not None
                else layer.GetName()
            )

            if cad_layer != selected_layer:
                continue

            ogr_geometry = feature.GetGeometryRef()

            if ogr_geometry is None:
                continue

            if not _is_line_geometry(
                    ogr_geometry):
                continue

            geometry = _qgs_geometry(
                ogr_geometry
            )

            if geometry and not geometry.isEmpty():
                geometries.append(
                    geometry
                )

        layer.ResetReading()

    return geometries


def _text_records(
    dataset,
    selected_layer
):
    records = []

    for layer_index in range(
            dataset.GetLayerCount()):
        layer = dataset.GetLayerByIndex(
            layer_index
        )
        definition = layer.GetLayerDefn()
        layer_field = _field_name(
            definition,
            LAYER_FIELD_CANDIDATES
        )
        text_field = _field_name(
            definition,
            TEXT_FIELD_CANDIDATES
        )

        if not text_field:
            continue

        layer.ResetReading()

        for feature in layer:
            cad_layer = (
                str(feature.GetField(layer_field)).strip()
                if layer_field
                and feature.GetField(layer_field) is not None
                else layer.GetName()
            )

            if cad_layer != selected_layer:
                continue

            value = feature.GetField(
                text_field
            )

            if value in [None, ""]:
                continue

            geometry = _qgs_geometry(
                feature.GetGeometryRef()
            )

            if not geometry or geometry.isEmpty():
                continue

            if QgsWkbTypes.geometryType(
                    geometry.wkbType()) == (
                    QgsWkbTypes.PointGeometry):
                point_geometry = geometry
            else:
                point_geometry = (
                    geometry.pointOnSurface()
                )

                if (
                        not point_geometry
                        or point_geometry.isEmpty()):
                    point_geometry = (
                        geometry.centroid()
                    )

            if point_geometry and not point_geometry.isEmpty():
                records.append((
                    point_geometry,
                    str(value).strip()
                ))

        layer.ResetReading()

    return records


def _memory_line_layer(geometries):
    layer = QgsVectorLayer(
        "MultiLineString",
        "ParcelForge Boundary Lines",
        "memory"
    )
    provider = layer.dataProvider()
    provider.addAttributes([
        QgsField(
            "source",
            QVariant.String
        )
    ])
    layer.updateFields()

    features = []

    for geometry in geometries:
        prepared = QgsGeometry(
            geometry
        )

        if QgsWkbTypes.isSingleType(
                prepared.wkbType()):
            prepared.convertToMultiType()

        feature = QgsFeature(
            layer.fields()
        )
        feature.setGeometry(
            prepared
        )
        feature["source"] = "DXF"
        features.append(feature)

    provider.addFeatures(features)
    layer.updateExtents()
    return layer


def _safe_field_name(
    requested,
    existing,
    shapefile
):
    cleaned = "".join(
        character
        if character.isalnum()
        or character == "_"
        else "_"
        for character in str(requested).strip()
    ).strip("_")

    if not cleaned:
        cleaned = "FIELD"

    if cleaned[0].isdigit():
        cleaned = "_" + cleaned

    maximum = 10 if shapefile else 63
    cleaned = cleaned[:maximum]

    candidate = cleaned
    counter = 2

    while candidate.upper() in existing:
        suffix = str(counter)
        candidate = (
            cleaned[:maximum - len(suffix)]
            + suffix
        )
        counter += 1

    existing.add(candidate.upper())
    return candidate


def _save_layer(layer, output_path):
    options = (
        QgsVectorFileWriter.SaveVectorOptions()
    )

    lower = output_path.lower()

    if lower.endswith(".gpkg"):
        options.driverName = "GPKG"
        options.layerName = (
            os.path.splitext(
                os.path.basename(output_path)
            )[0]
        )
        options.actionOnExistingFile = (
            QgsVectorFileWriter
            .CreateOrOverwriteFile
        )
    else:
        options.driverName = (
            "ESRI Shapefile"
        )
        options.fileEncoding = "UTF-8"
        options.actionOnExistingFile = (
            QgsVectorFileWriter
            .CreateOrOverwriteFile
        )

    result = (
        QgsVectorFileWriter
        .writeAsVectorFormatV3(
            layer,
            output_path,
            QgsProject.instance()
            .transformContext(),
            options
        )
    )

    error_code = result[0]

    if error_code != (
            QgsVectorFileWriter.NoError):
        error_message = (
            result[1]
            if len(result) > 1
            else "Unknown writer error"
        )
        raise RuntimeError(
            "Could not save output: {0}"
            .format(error_message)
        )


def build_parcel_attributes(
    dwg_path,
    boundary_layer,
    mappings,
    output_path,
    progress_callback=None
):
    if not mappings:
        raise RuntimeError(
            "At least one attribute mapping is required."
        )

    dataset = _open_dataset(dwg_path)

    if progress_callback:
        progress_callback(
            "Reading boundary lines..."
        )

    boundary_geometries = (
        _collect_boundary_geometries(
            dataset,
            boundary_layer
        )
    )

    if not boundary_geometries:
        raise RuntimeError(
            "The selected DXF boundary layer contains no usable line geometry."
        )

    line_layer = _memory_line_layer(
        boundary_geometries
    )

    if progress_callback:
        progress_callback(
            "Building polygons..."
        )

    polygon_result = processing.run(
        "native:polygonize",
        {
            "INPUT": line_layer,
            "KEEP_FIELDS": False,
            "OUTPUT": "TEMPORARY_OUTPUT",
        }
    )

    polygon_layer = polygon_result[
        "OUTPUT"
    ]

    if polygon_layer.featureCount() == 0:
        raise RuntimeError(
            "No polygons were created. Boundary lines must be clean, "
            "closed, and free from critical gaps or overlaps."
        )

    shapefile = output_path.lower().endswith(
        ".shp"
    )
    existing = {
        field.name().upper()
        for field in polygon_layer.fields()
    }

    final_mappings = []

    provider = polygon_layer.dataProvider()

    for field_name, text_layer in mappings:
        safe_name = _safe_field_name(
            field_name,
            existing,
            shapefile
        )
        provider.addAttributes([
            QgsField(
                safe_name,
                QVariant.String,
                len=254 if shapefile else 1000
            )
        ])
        final_mappings.append((
            safe_name,
            text_layer
        ))

    polygon_layer.updateFields()

    features = list(
        polygon_layer.getFeatures()
    )

    if not features:
        raise RuntimeError(
            "No polygon features are available for attribute mapping."
        )

    # Build the spatial index feature-by-feature for compatibility with
    # QGIS/PyQt builds that do not accept a Python list in the constructor.
    spatial_index = QgsSpatialIndex()

    for feature in features:
        try:
            spatial_index.addFeature(feature)
        except TypeError:
            # Older SIP bindings may expose insertFeature instead.
            insert_feature = getattr(
                spatial_index,
                "insertFeature",
                None
            )

            if insert_feature is None:
                raise

            insert_feature(feature)

    geometry_by_id = {
        feature.id(): QgsGeometry(
            feature.geometry()
        )
        for feature in features
    }
    values = {
        feature.id(): {
            field_name: []
            for field_name, _ in final_mappings
        }
        for feature in features
    }

    for mapping_number, (
            field_name,
            text_layer) in enumerate(
                final_mappings,
                1):
        if progress_callback:
            progress_callback(
                "Reading Attribute Mapping {0}..."
                .format(mapping_number)
            )

        for point_geometry, text_value in _text_records(
                dataset,
                text_layer):
            candidates = spatial_index.intersects(
                point_geometry.boundingBox()
            )

            destination_id = None

            for feature_id in candidates:
                polygon_geometry = geometry_by_id[
                    feature_id
                ]

                if (
                        polygon_geometry.contains(
                            point_geometry)
                        or polygon_geometry.intersects(
                            point_geometry)):
                    destination_id = feature_id
                    break

            if destination_id is None:
                continue

            field_values = values[
                destination_id
            ][field_name]

            if text_value not in field_values:
                field_values.append(
                    text_value
                )

    polygon_layer.startEditing()

    for feature in polygon_layer.getFeatures():
        for field_name, _ in final_mappings:
            field_index = polygon_layer.fields().indexOf(
                field_name
            )
            combined = " | ".join(
                values[feature.id()][
                    field_name
                ]
            )

            if shapefile:
                combined = combined[:254]

            polygon_layer.changeAttributeValue(
                feature.id(),
                field_index,
                combined
            )

    if not polygon_layer.commitChanges():
        raise RuntimeError(
            "Could not write mapped attributes to the polygon layer."
        )

    if progress_callback:
        progress_callback(
            "Saving output..."
        )

    _save_layer(
        polygon_layer,
        output_path
    )

    return {
        "polygon_count": polygon_layer.featureCount(),
        "output_path": output_path,
        "fields": [
            name
            for name, _ in final_mappings
        ],
    }
