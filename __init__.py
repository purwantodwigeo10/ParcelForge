# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later

def classFactory(iface):
    from .parcelforge_plugin import ParcelForgePlugin
    return ParcelForgePlugin(iface)
