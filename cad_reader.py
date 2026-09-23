# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read DXF entities, build parcel polygons, and map text attributes."""

import os

from osgeo import ogr

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

from .output_safety import ensure_new_output
from .qgis_compat import (
    GEOMETRY_POINT,
    WRITER_CREATE_OR_OVERWRITE_FILE,
    WRITER_NO_ERROR,
)
from .qt_compat import FIELD_STRING


MAX_MAPPINGS = 10


class ParcelForgeCanceled(RuntimeError):
    """Raised when the user cancels a processing operation."""


def _is_canceled(feedback):
    return bool(
        feedback is not None
        and feedback.isCanceled()
    )


def _check_canceled(feedback):
    if _is_canceled(feedback):
        raise ParcelForgeCanceled(
            "ParcelForge was canceled. No output was written."
        )


def _report(progress_callback, message, percent):
    if progress_callback:
        progress_callback(message, percent)


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

    result = (
        sorted(
            boundary_layers,
            key=str.upper
        ),
        sorted(
            text_layers,
            key=str.upper
        ),
    )
    dataset = None
    return result


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
                    geometry.wkbType()) == GEOMETRY_POINT:
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

            text_value = str(value).strip()

            if (
                    text_value
                    and point_geometry
                    and not point_geometry.isEmpty()):
                records.append((
                    point_geometry,
                    text_value
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
    if not provider.addAttributes([
        QgsField(
            "source",
            FIELD_STRING
        )
    ]):
        raise RuntimeError(
            "Could not create the temporary boundary field."
        )
    layer.updateFields()

    features = []

    for geometry in geometries:
        prepared = QgsGeometry(
            geometry
        )
        prepared.convertToStraightSegment()

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

    added, _ = provider.addFeatures(features)
    if not added or layer.featureCount() != len(features):
        raise RuntimeError("Some boundary geometries could not be loaded.")
    layer.updateExtents()
    return layer


def _validate_mappings(mappings):
    if not mappings:
        raise RuntimeError(
            "At least one attribute mapping is required."
        )

    if len(mappings) > MAX_MAPPINGS:
        raise RuntimeError(
            "ParcelForge supports a maximum of {0} attribute mappings."
            .format(MAX_MAPPINGS)
        )

    validated = []

    for number, mapping in enumerate(mappings, 1):
        if not isinstance(mapping, (list, tuple)) or len(mapping) != 2:
            raise RuntimeError(
                "Attribute Mapping {0} is invalid."
                .format(number)
            )

        field_name = str(mapping[0] or "").strip()
        text_layer = str(mapping[1] or "").strip()

        if not field_name:
            raise RuntimeError(
                "Attribute Mapping {0} has no output field name."
                .format(number)
            )

        if not text_layer:
            raise RuntimeError(
                "Attribute Mapping {0} has no source text layer."
                .format(number)
            )

        validated.append((field_name, text_layer))

    return validated


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


def _resolve_destination(
    candidates,
    geometry_by_id,
    point_geometry,
    text_value
):
    """Return one containing polygon ID or reject an ambiguous label."""
    intersections = []
    destinations = []

    for feature_id in candidates:
        polygon_geometry = geometry_by_id.get(
            feature_id
        )

        if (
                polygon_geometry is not None
                and polygon_geometry.intersects(point_geometry)):
            intersections.append(feature_id)

            if polygon_geometry.contains(point_geometry):
                destinations.append(feature_id)

    if len(intersections) > 1 or len(destinations) > 1:
        raise RuntimeError(
            "Text label '{0}' touches or overlaps more than one polygon. "
            "Move it clearly inside its intended polygon and retry."
            .format(text_value)
        )

    if intersections and not destinations:
        raise RuntimeError(
            "Text label '{0}' lies on a polygon boundary. Move it clearly "
            "inside its intended polygon and retry."
            .format(text_value)
        )

    return destinations[0] if destinations else None


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
            WRITER_CREATE_OR_OVERWRITE_FILE
        )
    else:
        options.driverName = (
            "ESRI Shapefile"
        )
        options.fileEncoding = "UTF-8"
        options.actionOnExistingFile = (
            WRITER_CREATE_OR_OVERWRITE_FILE
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

    if error_code != WRITER_NO_ERROR:
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
    progress_callback=None,
    source_crs=None,
    feedback=None
):
    if source_crs is None or not source_crs.isValid():
        raise RuntimeError(
            "The actual DXF coordinate reference system must be specified."
        )

    boundary_layer = str(boundary_layer or "").strip()

    if not boundary_layer:
        raise RuntimeError(
            "A DXF boundary line layer must be selected."
        )

    mappings = _validate_mappings(mappings)

    if not output_path.lower().endswith((".shp", ".gpkg")):
        raise RuntimeError("Output must use .shp or .gpkg extension.")

    _check_canceled(feedback)
    ensure_new_output(output_path)
    dataset = _open_dataset(dwg_path)

    _report(
        progress_callback,
        "Reading boundary lines...",
        8
    )
    _check_canceled(feedback)

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

    line_layer.setCrs(source_crs)

    _report(
        progress_callback,
        "Building polygons...",
        20
    )
    _check_canceled(feedback)

    try:
        polygon_result = processing.run(
            "native:polygonize",
            {
                "INPUT": line_layer,
                "KEEP_FIELDS": False,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
            feedback=feedback
        )
    except Exception:
        _check_canceled(feedback)
        raise

    _check_canceled(feedback)

    polygon_layer = polygon_result[
        "OUTPUT"
    ]

    if not hasattr(polygon_layer, "featureCount"):
        polygon_layer = QgsVectorLayer(
            str(polygon_layer),
            "ParcelForge Polygons",
            "ogr"
        )

    if not polygon_layer.isValid():
        raise RuntimeError(
            "QGIS did not return a valid polygon layer."
        )

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
    new_fields = []

    for field_name, text_layer in mappings:
        safe_name = _safe_field_name(
            field_name,
            existing,
            shapefile
        )
        if shapefile:
            new_field = QgsField(
                safe_name,
                FIELD_STRING,
                len=254
            )
        else:
            new_field = QgsField(
                safe_name,
                FIELD_STRING
            )

        new_fields.append(new_field)
        final_mappings.append((
            safe_name,
            text_layer
        ))

    if not provider.addAttributes(new_fields):
        raise RuntimeError(
            "Could not create one or more output attribute fields."
        )

    polygon_layer.updateFields()

    missing_fields = [
        field_name
        for field_name, _ in final_mappings
        if polygon_layer.fields().indexOf(field_name) < 0
    ]

    if missing_fields:
        raise RuntimeError(
            "QGIS did not create the requested output field(s): {0}"
            .format(", ".join(missing_fields))
        )

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
    mapping_stats = []
    mapping_total = len(final_mappings)

    for mapping_number, (
            field_name,
            text_layer) in enumerate(
                final_mappings,
                1):
        percent = 30 + int(
            50 * (mapping_number - 1) / mapping_total
        )
        _report(
            progress_callback,
            "Reading Attribute Mapping {0} of {1}..."
            .format(mapping_number, mapping_total),
            percent
        )
        _check_canceled(feedback)

        text_records = _text_records(
            dataset,
            text_layer
        )

        if not text_records:
            raise RuntimeError(
                "No usable text was found on DXF layer '{0}' for field "
                "'{1}'."
                .format(text_layer, field_name)
            )

        mapped_count = 0
        outside_count = 0
        duplicate_count = 0

        for record_number, (
                point_geometry,
                text_value) in enumerate(text_records, 1):
            if record_number % 100 == 0:
                record_fraction = (
                    record_number / len(text_records)
                )
                mapping_fraction = (
                    mapping_number - 1 + record_fraction
                ) / mapping_total
                _report(
                    progress_callback,
                    "Mapping field '{0}' ({1}/{2} labels)..."
                    .format(
                        field_name,
                        record_number,
                        len(text_records)
                    ),
                    30 + int(50 * mapping_fraction)
                )
                _check_canceled(feedback)

            candidates = spatial_index.intersects(
                point_geometry.boundingBox()
            )
            destination_id = _resolve_destination(
                candidates,
                geometry_by_id,
                point_geometry,
                text_value
            )

            if destination_id is None:
                outside_count += 1
                continue

            mapped_count += 1

            field_values = values[
                destination_id
            ][field_name]

            if text_value not in field_values:
                field_values.append(
                    text_value
                )
            else:
                duplicate_count += 1

        if mapped_count == 0:
            raise RuntimeError(
                "None of the text on DXF layer '{0}' is strictly inside a "
                "created polygon. Check the selected layers and DXF CRS."
                .format(text_layer)
            )

        multi_value_count = sum(
            1
            for feature_values in values.values()
            if len(feature_values[field_name]) > 1
        )
        mapping_stats.append({
            "output_field": field_name,
            "source_layer": text_layer,
            "read": len(text_records),
            "mapped": mapped_count,
            "outside": outside_count,
            "duplicates_ignored": duplicate_count,
            "multi_value_polygons": multi_value_count,
        })

    _check_canceled(feedback)

    if not polygon_layer.startEditing():
        raise RuntimeError(
            "Could not start editing the temporary polygon layer."
        )

    field_indices = {
        field_name: polygon_layer.fields().indexOf(field_name)
        for field_name, _ in final_mappings
    }

    for feature in polygon_layer.getFeatures():
        _check_canceled(feedback)

        for field_name, _ in final_mappings:
            field_index = field_indices[field_name]
            combined = " | ".join(
                values[feature.id()][
                    field_name
                ]
            )

            if shapefile:
                combined = combined[:254]

            if not polygon_layer.changeAttributeValue(
                feature.id(),
                field_index,
                combined
            ):
                polygon_layer.rollBack()
                raise RuntimeError(
                    "Could not set field '{0}' on polygon feature {1}."
                    .format(field_name, feature.id())
                )

    if not polygon_layer.commitChanges():
        errors = "; ".join(
            polygon_layer.commitErrors()
        )
        polygon_layer.rollBack()
        raise RuntimeError(
            "Could not write mapped attributes to the polygon layer.{0}"
            .format(" " + errors if errors else "")
        )

    _report(
        progress_callback,
        "Saving output...",
        90
    )
    _check_canceled(feedback)

    # Re-check immediately before writing so a file created during processing
    # is not silently replaced.
    ensure_new_output(output_path)

    _save_layer(
        polygon_layer,
        output_path
    )

    _report(
        progress_callback,
        "Completed successfully.",
        100
    )

    return {
        "polygon_count": polygon_layer.featureCount(),
        "output_path": output_path,
        "fields": [
            name
            for name, _ in final_mappings
        ],
        "mapping_stats": mapping_stats,
        "labels_read": sum(
            item["read"] for item in mapping_stats
        ),
        "labels_mapped": sum(
            item["mapped"] for item in mapping_stats
        ),
        "labels_outside": sum(
            item["outside"] for item in mapping_stats
        ),
        "multi_value_polygons": sum(
            item["multi_value_polygons"]
            for item in mapping_stats
        ),
    }
