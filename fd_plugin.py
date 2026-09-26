# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""QGIS plugin entry point for Find Duplicate."""

import os

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtGui import QDesktopServices, QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox

from .fd_dialog import FindDuplicateDialog, HELP_URL


class FindDuplicatePlugin(object):
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.help_action = None
        self.menu = 'RUANG SPASIAL'
        self.dialog = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        self.action = QAction(
            QIcon(icon_path),
            'Find Duplicate',
            self.iface.mainWindow())
        self.action.setObjectName('FindDuplicateAction')
        self.action.triggered.connect(self.run)
        self.iface.addPluginToVectorMenu(self.menu, self.action)
        self.iface.addToolBarIcon(self.action)

        self.help_action = QAction(
            'Find Duplicate Help',
            self.iface.mainWindow())
        self.help_action.setObjectName('FindDuplicateHelpAction')
        self.help_action.triggered.connect(self.open_help)
        self.iface.addPluginToVectorMenu(self.menu, self.help_action)

    def unload(self):
        if self.action:
            self.iface.removePluginVectorMenu(self.menu, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.help_action:
            self.iface.removePluginVectorMenu(self.menu, self.help_action)
            self.help_action = None

    def run(self):
        self.dialog = FindDuplicateDialog(self.iface)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def open_help(self):
        if not QDesktopServices.openUrl(QUrl(HELP_URL)):
            QMessageBox.warning(
                self.iface.mainWindow(),
                'Find Duplicate',
                'The help page could not be opened in the web browser.')
