# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later

import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .parcelforge_dialog import ParcelForgeDialog


class ParcelForgePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(
            os.path.abspath(__file__)
        )
        self.action = None
        self.dialog = None

    def initGui(self):
        self.action = QAction(
            QIcon(
                os.path.join(
                    self.plugin_dir,
                    "icon.png"
                )
            ),
            "ParcelForge",
            self.iface.mainWindow()
        )
        self.action.setObjectName(
            "ParcelForgeAction"
        )
        self.action.triggered.connect(
            self.run
        )

        self.iface.addPluginToVectorMenu(
            "ParcelForge",
            self.action
        )
        self.iface.addToolBarIcon(
            self.action
        )

    def unload(self):
        if self.action is not None:
            self.iface.removePluginVectorMenu(
                "ParcelForge",
                self.action
            )
            self.iface.removeToolBarIcon(
                self.action
            )
            self.action.deleteLater()
            self.action = None

        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        if self.dialog is None:
            self.dialog = ParcelForgeDialog(
                self.iface,
                self.plugin_dir,
                self.iface.mainWindow()
            )

        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
