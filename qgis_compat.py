# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Small compatibility helpers for QGIS enum changes."""

from qgis.core import QgsVectorFileWriter, QgsWkbTypes


def _enum_member(container, scoped_name, member_name):
    """Return a scoped QGIS enum member with a QGIS 3 fallback."""
    scoped_enum = getattr(container, scoped_name, None)

    if scoped_enum is not None:
        member = getattr(scoped_enum, member_name, None)

        if member is not None:
            return member

    return getattr(container, member_name)


GEOMETRY_POINT = _enum_member(
    QgsWkbTypes,
    "GeometryType",
    "PointGeometry"
)

WRITER_CREATE_OR_OVERWRITE_FILE = _enum_member(
    QgsVectorFileWriter,
    "ActionOnExistingFile",
    "CreateOrOverwriteFile"
)

WRITER_NO_ERROR = _enum_member(
    QgsVectorFileWriter,
    "WriterError",
    "NoError"
)
