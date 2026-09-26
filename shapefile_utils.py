# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Recoverable replacement helpers for a multi-file Shapefile dataset."""

import os


SHAPEFILE_EXTENSIONS = (
    '.shp',
    '.shx',
    '.dbf',
    '.prj',
    '.cpg',
    '.qpj',
    '.fix',
    '.sbn',
    '.sbx',
)


def commit_shapefile(temporary_path, output_path):
    """Replace a Shapefile family and restore the old one on failure."""
    temporary_base = os.path.splitext(temporary_path)[0]
    output_base = os.path.splitext(output_path)[0]
    backup_directory = os.path.join(
        os.path.dirname(temporary_path),
        'previous_output')
    os.makedirs(backup_directory, exist_ok=True)
    backup_base = os.path.join(
        backup_directory,
        os.path.basename(output_base))

    backed_up = []
    installed = []
    try:
        for extension in SHAPEFILE_EXTENSIONS:
            existing = output_base + extension
            if os.path.exists(existing):
                os.replace(existing, backup_base + extension)
                backed_up.append(extension)

        for extension in SHAPEFILE_EXTENSIONS:
            generated = temporary_base + extension
            if os.path.exists(generated):
                os.replace(generated, output_base + extension)
                installed.append(extension)
        if '.shp' not in installed:
            raise OSError('The generated .shp component is missing.')
    except OSError as error:
        rollback_errors = []
        for extension in reversed(installed):
            destination = output_base + extension
            try:
                if os.path.exists(destination):
                    os.replace(destination, temporary_base + extension)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        for extension in reversed(backed_up):
            backup = backup_base + extension
            try:
                if os.path.exists(backup):
                    os.replace(backup, output_base + extension)
            except OSError as rollback_error:
                rollback_errors.append(str(rollback_error))
        message = 'Could not replace the output Shapefile: %s.' % error
        if rollback_errors:
            message += ' Rollback warning: %s' % '; '.join(rollback_errors)
        raise RuntimeError(message) from error
