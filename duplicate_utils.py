# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Pure helpers for duplicate comparison and Shapefile field names."""

import re


def value_key(value):
    """Return a stable, hashable key without changing case or spaces."""
    if value is None:
        return ('NULL', '')
    return (type(value).__name__, str(value))


def format_xy(location):
    """Return a compact semicolon-separated coordinate pair."""
    if location is None:
        return ''
    return '%s;%s' % (
        format(location[0], '.15g'),
        format(location[1], '.15g'),
    )


def unique_dbf_name(name, used_names):
    """Create a unique DBF field name with a ten-character limit."""
    cleaned = re.sub(r'[^A-Za-z0-9_]', '_', str(name or 'FIELD'))
    cleaned = cleaned.strip('_') or 'FIELD'
    if cleaned[0].isdigit():
        cleaned = 'F_' + cleaned
    base = cleaned[:10]
    candidate = base
    counter = 2
    while candidate.upper() in used_names:
        suffix = '_%s' % counter
        candidate = base[:10 - len(suffix)] + suffix
        counter += 1
    used_names.add(candidate.upper())
    return candidate
