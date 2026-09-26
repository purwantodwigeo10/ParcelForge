# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""ParcelForge dialogs and processing workflow."""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsProcessingFeedback,
    QgsProject,
    QgsVectorLayer,
)
from qgis.gui import QgsProjectionSelectionWidget

from . import cad_reader
from . import license_manager
from .output_safety import ensure_new_output
from .qt_compat import run_dialog_or_loop
from .run_guard import single_run


APP_STYLE = """
QDialog {
    background: #f7f8fa;
    color: #30343a;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 9pt;
}

QFrame#topBar,
QFrame#bottomBar {
    background: #ffffff;
    border: 1px solid #e2e5e9;
    border-radius: 9px;
}

QGroupBox[role="section"] {
    background: #ffffff;
    border: 1px solid #dfe3e7;
    border-radius: 8px;
    margin-top: 12px;
    padding: 9px 9px 8px 9px;
    font-weight: 600;
    color: #34383d;
}

QGroupBox[role="section"]::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 5px;
    background: #f7f8fa;
    color: #34383d;
    font-size: 9.5pt;
    font-weight: 700;
}

QGroupBox[role="mapping"] {
    background: #fcfcfd;
    border: 1px solid #e4e7eb;
    border-left: 3px solid #ff6a00;
    border-radius: 7px;
    margin-top: 10px;
    padding: 7px 8px 7px 8px;
    font-weight: 600;
    color: #444a50;
}

QGroupBox[role="mapping"]::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 9px;
    padding: 0 4px;
    background: #fcfcfd;
    color: #c85400;
    font-size: 9pt;
    font-weight: 700;
}

QLabel#smallText {
    color: #737a82;
    font-size: 8.5pt;
}

QLabel#statusPill {
    border-radius: 8px;
    padding: 2px 6px;
    font-size: 7.8pt;
    font-weight: 700;
    min-height: 18px;
    max-height: 21px;
}

QLabel#progressLabel {
    background: #fff8f3;
    border: 1px solid #ffd9bd;
    border-radius: 7px;
    color: #8b460c;
    padding: 5px 8px;
    font-size: 8.5pt;
}

QProgressBar {
    min-height: 14px;
    max-height: 14px;
    border: 1px solid #d7dbe0;
    border-radius: 6px;
    background: #ffffff;
    color: #5d636a;
    text-align: center;
    font-size: 7.5pt;
}

QProgressBar::chunk {
    background: #ff8a38;
    border-radius: 5px;
}

QLineEdit,
QComboBox,
QSpinBox {
    min-height: 25px;
    max-height: 29px;
    padding: 2px 6px;
    border: 1px solid #cfd4da;
    border-radius: 5px;
    background: #ffffff;
    selection-background-color: #ff6a00;
}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus {
    border-color: #ff6a00;
}

QComboBox::drop-down {
    border: 0;
    width: 24px;
}

QPushButton {
    min-height: 23px;
    max-height: 26px;
    padding: 1px 7px;
    border: 1px solid #cfd4da;
    border-radius: 6px;
    background: #ffffff;
    color: #3b4046;
    font-weight: 600;
}

QPushButton:hover {
    background: #fff8f3;
    border-color: #ff9a55;
    color: #c65300;
}

QPushButton#primaryButton {
    min-height: 27px;
    background: #ff6a00;
    border-color: #e45f00;
    color: #ffffff;
    font-weight: 700;
}

QPushButton#primaryButton:hover {
    background: #e95e00;
    color: #ffffff;
}

QPushButton#linkButton {
    background: #fffaf6;
    border-color: #f2c9aa;
    color: #bd5108;
}

QScrollArea {
    border: 0;
    background: transparent;
}

QScrollArea > QWidget > QWidget {
    background: transparent;
}

QScrollBar:vertical {
    width: 9px;
    background: #eef0f3;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #c6cbd1;
    border-radius: 4px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #aeb5bd;
}
"""


def _qt_window_flag(flag_name):
    """
    Return a window flag that works with both Qt5-style and Qt6-style enums.
    """
    direct_flag = getattr(Qt, flag_name, None)

    if direct_flag is not None:
        return direct_flag

    window_type = getattr(Qt, "WindowType", None)

    if window_type is not None:
        return getattr(window_type, flag_name, None)

    return None


def _enable_standard_window_controls(dialog):
    """
    Add minimize, maximize, and close buttons without changing the compact
    initial dialog size.
    """
    flags = dialog.windowFlags()

    for flag_name in [
            "WindowMinimizeButtonHint",
            "WindowMaximizeButtonHint",
            "WindowCloseButtonHint"]:
        flag = _qt_window_flag(flag_name)

        if flag is not None:
            flags = flags | flag

    dialog.setWindowFlags(flags)
    dialog.setSizeGripEnabled(True)


class ResponsiveProcessingFeedback(QgsProcessingFeedback):
    """Keep the Cancel button responsive during a QGIS algorithm."""

    def setProgress(self, progress):
        super().setProgress(progress)
        QApplication.processEvents()


class ActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("ParcelForge — Manage Activation")
        _enable_standard_window_controls(self)
        self.setMinimumWidth(585)
        self.setStyleSheet(APP_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        group = QGroupBox("Activation and User Guide")
        group.setProperty("role", "section")

        form = QFormLayout(group)
        form.setContentsMargins(9, 12, 9, 8)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(6)

        self.status_value = QLineEdit()
        self.status_value.setReadOnly(True)

        self.device_value = QLineEdit(license_manager.device_id())
        self.device_value.setReadOnly(True)

        self.code_value = QLineEdit()
        self.code_value.setPlaceholderText("Enter activation code")

        form.addRow("Activation Status", self.status_value)
        form.addRow("Device ID", self.device_value)
        form.addRow("Activation Code", self.code_value)

        root.addWidget(group)

        action_bar = QFrame()
        action_bar.setObjectName("bottomBar")

        actions = QHBoxLayout(action_bar)
        actions.setContentsMargins(8, 6, 8, 6)
        actions.setSpacing(6)

        self.request_button = QPushButton("Request Page")
        self.request_button.setObjectName("linkButton")

        self.guide_button = QPushButton("User Guide")
        self.guide_button.setObjectName("linkButton")

        self.activate_button = QPushButton("Activate / Refresh")
        self.activate_button.setObjectName("primaryButton")

        self.close_button = QPushButton("Close")

        actions.addWidget(self.request_button)
        actions.addWidget(self.guide_button)
        actions.addStretch(1)
        actions.addWidget(self.activate_button)
        actions.addWidget(self.close_button)

        root.addWidget(action_bar)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        root.addWidget(self.message_label)

        self.request_button.clicked.connect(
            license_manager.open_request_page
        )
        self.guide_button.clicked.connect(
            license_manager.open_user_guide
        )
        self.activate_button.clicked.connect(
            self.activate_or_refresh
        )
        self.close_button.clicked.connect(self.accept)

        self.refresh_display()

    def refresh_display(self):
        status = license_manager.status_info(
            False
        )
        self.status_value.setText(
            status["short_text"]
        )
        self.status_value.setToolTip(
            status["detail"]
        )

    def activate_or_refresh(self):
        code = self.code_value.text().strip()

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.activate_button.setEnabled(False)

        try:
            if code:
                success, message = license_manager.activate(code)
            else:
                result, message = license_manager.refresh()
                success = result is True

            self.refresh_display()

            if success:
                self.message_label.setStyleSheet(
                    "color:#1565c0; font-weight:600; padding:4px;"
                )
            else:
                self.message_label.setStyleSheet(
                    "color:#b42318; font-weight:600; padding:4px;"
                )

            self.message_label.setText(message)

        except Exception as exc:
            self.message_label.setStyleSheet(
                "color:#b42318; font-weight:600; padding:4px;"
            )
            self.message_label.setText(
                "Activation could not be completed: {0}"
                .format(exc)
            )

        finally:
            self.activate_button.setEnabled(True)
            QApplication.restoreOverrideCursor()


class ParcelForgeDialog(QDialog):
    MAX_MAPPINGS = 10

    def __init__(self, iface, plugin_dir, parent=None):
        super().__init__(parent)

        self.iface = iface
        self.plugin_dir = plugin_dir
        self.mapping_rows = []
        self.processing_feedback = None

        self.setWindowTitle(
            "ParcelForge — DXF Polygon and Attribute Builder"
        )
        _enable_standard_window_controls(self)
        self.resize(760, 680)
        self.setMinimumSize(700, 560)
        self.setStyleSheet(APP_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(11, 11, 11, 11)
        root.setSpacing(7)

        # Compact header
        top_bar = QFrame()
        top_bar.setObjectName("topBar")

        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(8, 4, 8, 4)
        top_layout.setSpacing(5)

        logo_label = QLabel()
        logo_pixmap = QPixmap(
            os.path.join(plugin_dir, "logo.png")
        )
        logo_label.setPixmap(
            logo_pixmap.scaled(
                150,
                31,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )
        logo_label.setFixedWidth(156)
        top_layout.addWidget(logo_label)

        subtitle = QLabel(
            "DXF Polygon and Attribute Builder"
        )
        subtitle.setObjectName("smallText")
        top_layout.addWidget(subtitle)

        top_layout.addStretch(1)

        header_actions = QVBoxLayout()
        header_actions.setContentsMargins(0, 0, 0, 0)
        header_actions.setSpacing(4)

        self.status_label = QLabel()
        self.status_label.setObjectName("statusPill")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumWidth(92)
        self.status_label.setMaximumWidth(112)

        self.activation_button = QPushButton("Activate")
        self.guide_button = QPushButton("User Guide")
        self.guide_button.setObjectName("linkButton")

        self.activation_button.setFixedWidth(74)
        self.guide_button.setFixedWidth(86)

        header_actions.addWidget(
            self.status_label,
            0,
            Qt.AlignRight
        )
        header_actions.addWidget(
            self.activation_button,
            0,
            Qt.AlignRight
        )
        header_actions.addWidget(
            self.guide_button,
            0,
            Qt.AlignRight
        )

        top_layout.addLayout(header_actions)

        root.addWidget(top_bar)

        # Input frame
        input_group = QGroupBox("Input CAD Data")
        input_group.setProperty("role", "section")

        input_form = QFormLayout(input_group)
        input_form.setContentsMargins(9, 13, 9, 8)
        input_form.setHorizontalSpacing(14)
        input_form.setVerticalSpacing(6)

        dwg_widget = QWidget()
        dwg_row = QHBoxLayout(dwg_widget)
        dwg_row.setContentsMargins(0, 0, 0, 0)
        dwg_row.setSpacing(5)

        self.dwg_path = QLineEdit()
        self.dwg_path.setPlaceholderText("Select DXF file")

        self.dwg_browse = QPushButton("Browse")
        self.dwg_browse.setFixedWidth(72)

        dwg_row.addWidget(self.dwg_path, 1)
        dwg_row.addWidget(self.dwg_browse)

        self.boundary_combo = QComboBox()
        self.boundary_combo.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed
        )

        input_form.addRow("Input DXF File", dwg_widget)
        input_form.addRow(
            "Boundary Line Layer",
            self.boundary_combo
        )

        self.source_crs = QgsProjectionSelectionWidget()
        self.source_crs.setCrs(QgsCoordinateReferenceSystem())
        input_form.addRow("DXF CRS (assign only)", self.source_crs)
        root.addWidget(input_group)

        # Attribute mapping frame
        mapping_group = QGroupBox(
            "Attribute Mapping Configuration"
        )
        mapping_group.setProperty("role", "section")

        mapping_layout = QVBoxLayout(mapping_group)
        mapping_layout.setContentsMargins(8, 13, 8, 8)
        mapping_layout.setSpacing(5)

        count_widget = QWidget()
        count_row = QHBoxLayout(count_widget)
        count_row.setContentsMargins(0, 0, 0, 0)
        count_row.setSpacing(7)

        count_label = QLabel(
            "Number of Attribute Mappings"
        )
        count_label.setStyleSheet(
            "font-weight:600; color:#4b5056;"
        )

        self.mapping_count = QSpinBox()
        self.mapping_count.setRange(
            1,
            self.MAX_MAPPINGS
        )
        self.mapping_count.setValue(3)
        self.mapping_count.setFixedWidth(65)

        count_row.addWidget(count_label)
        count_row.addWidget(self.mapping_count)
        count_row.addStretch(1)

        mapping_layout.addWidget(count_widget)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        self.mapping_container = QVBoxLayout(
            scroll_content
        )
        self.mapping_container.setContentsMargins(
            1, 1, 3, 1
        )
        self.mapping_container.setSpacing(5)

        for number in range(
                1,
                self.MAX_MAPPINGS + 1):

            row_group = QGroupBox(
                "Attribute Mapping {0}".format(number)
            )
            row_group.setProperty("role", "mapping")

            row_form = QFormLayout(row_group)
            row_form.setContentsMargins(8, 11, 8, 7)
            row_form.setHorizontalSpacing(12)
            row_form.setVerticalSpacing(4)

            field_name = QLineEdit()
            field_name.setPlaceholderText(
                "Example: OBJECT_ID"
            )

            source_layer = QComboBox()
            source_layer.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Fixed
            )

            row_form.addRow(
                "Output Field Name",
                field_name
            )
            row_form.addRow(
                "Source Text Layer",
                source_layer
            )

            self.mapping_container.addWidget(
                row_group
            )

            self.mapping_rows.append({
                "group": row_group,
                "field": field_name,
                "layer": source_layer,
            })

        self.mapping_container.addStretch(1)
        scroll.setWidget(scroll_content)
        mapping_layout.addWidget(scroll)

        root.addWidget(mapping_group, 1)

        # Output frame
        output_group = QGroupBox("Output")
        output_group.setProperty("role", "section")

        output_form = QFormLayout(output_group)
        output_form.setContentsMargins(9, 13, 9, 8)
        output_form.setHorizontalSpacing(14)

        output_widget = QWidget()
        output_row = QHBoxLayout(output_widget)
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.setSpacing(5)

        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText(
            "Save as GeoPackage or Shapefile"
        )

        self.output_browse = QPushButton("Browse")
        self.output_browse.setFixedWidth(72)

        output_row.addWidget(self.output_path, 1)
        output_row.addWidget(self.output_browse)

        output_form.addRow(
            "Output Polygon Layer",
            output_widget
        )

        root.addWidget(output_group)

        self.progress_label = QLabel("Ready.")
        self.progress_label.setObjectName("progressLabel")
        self.progress_label.setWordWrap(True)
        root.addWidget(self.progress_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        root.addWidget(self.progress_bar)

        # Compact action bar
        bottom_bar = QFrame()
        bottom_bar.setObjectName("bottomBar")

        bottom = QHBoxLayout(bottom_bar)
        bottom.setContentsMargins(8, 6, 8, 6)
        bottom.setSpacing(6)

        bottom.addStretch(1)

        self.run_button = QPushButton(
            "Run ParcelForge"
        )
        self.run_button.setObjectName(
            "primaryButton"
        )
        self.run_button.setMinimumWidth(145)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumWidth(80)
        self.cancel_button.setEnabled(False)

        self.close_button = QPushButton("Close")
        self.close_button.setMinimumWidth(90)

        bottom.addWidget(self.run_button)
        bottom.addWidget(self.cancel_button)
        bottom.addWidget(self.close_button)

        root.addWidget(bottom_bar)

        self.dwg_browse.clicked.connect(
            self.select_dwg
        )
        self.dwg_path.editingFinished.connect(
            self.load_cad_layers
        )
        self.output_browse.clicked.connect(
            self.select_output
        )
        self.mapping_count.valueChanged.connect(
            self.update_mapping_visibility
        )
        self.activation_button.clicked.connect(
            self.open_activation
        )
        self.guide_button.clicked.connect(
            license_manager.open_user_guide
        )
        self.run_button.clicked.connect(
            self.run_process
        )
        self.cancel_button.clicked.connect(
            self.cancel_process
        )
        self.close_button.clicked.connect(
            self.reject
        )

        self.update_mapping_visibility()
        self.refresh_status()

    def showEvent(self, event):
        self.refresh_status()
        super().showEvent(event)

    def refresh_status(self):
        status = license_manager.status_info(
            False
        )
        mode = status["mode"]

        self.status_label.setText(
            status["short_text"]
        )
        self.status_label.setToolTip(
            status["detail"]
        )

        common = (
            "border-radius:8px;"
            "padding:2px 6px;"
            "font-size:7.8pt;"
            "font-weight:700;"
        )

        if mode == "active":
            self.status_label.setStyleSheet(
                common
                + "background:#edf8f1;"
                + "border:1px solid #b7dfc5;"
                + "color:#176d38;"
            )
        elif mode == "trial":
            self.status_label.setStyleSheet(
                common
                + "background:#fff8e9;"
                + "border:1px solid #eed08b;"
                + "color:#885900;"
            )
        else:
            self.status_label.setStyleSheet(
                common
                + "background:#fff1f0;"
                + "border:1px solid #e7b1ad;"
                + "color:#a12b24;"
            )

    def update_mapping_visibility(self):
        count = self.mapping_count.value()

        for index, row in enumerate(
                self.mapping_rows,
                1):
            row["group"].setVisible(
                index <= count
            )

    def select_dwg(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select DXF File",
            "",
            "AutoCAD DXF (*.dxf)"
        )

        if not path:
            return

        self.dwg_path.setText(path)
        self.load_cad_layers()

    def load_cad_layers(self):
        path = self.dwg_path.text().strip()

        if not path:
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.progress_bar.setValue(0)
        self.progress_label.setText(
            "Reading DXF layers..."
        )

        try:
            boundary_layers, text_layers = (
                cad_reader.scan_layers(path)
            )

            self.boundary_combo.clear()
            self.boundary_combo.addItems(
                boundary_layers
            )

            for row in self.mapping_rows:
                current = (
                    row["layer"].currentText()
                )
                row["layer"].clear()
                row["layer"].addItems(
                    text_layers
                )

                if current in text_layers:
                    row["layer"].setCurrentText(
                        current
                    )

            if not boundary_layers:
                QMessageBox.warning(
                    self,
                    "ParcelForge",
                    "No line-based DXF layers were found."
                )

            if not text_layers:
                QMessageBox.warning(
                    self,
                    "ParcelForge",
                    "No readable DXF text layers were found."
                )

            self.progress_label.setText(
                "Ready. Loaded {0} boundary layer(s) and "
                "{1} text layer(s). Progress will start from 0%.".format(
                    len(boundary_layers),
                    len(text_layers)
                )
            )
            self.progress_bar.setValue(0)

        except Exception as exc:
            self.progress_label.setText(
                "Could not read the DXF file."
            )
            self.progress_bar.setValue(0)
            QMessageBox.critical(
                self,
                "ParcelForge",
                str(exc)
            )

        finally:
            QApplication.restoreOverrideCursor()

    def select_output(self):
        path, selected_filter = (
            QFileDialog.getSaveFileName(
                self,
                "Save Output Polygon Layer",
                "",
                (
                    "GeoPackage (*.gpkg);;"
                    "ESRI Shapefile (*.shp)"
                )
            )
        )

        if not path:
            return

        if not path.lower().endswith(
                (".gpkg", ".shp")):

            if "Shapefile" in selected_filter:
                path += ".shp"
            else:
                path += ".gpkg"

        self.output_path.setText(path)

    def open_activation(self):
        dialog = ActivationDialog(self)
        run_dialog_or_loop(dialog)
        self.refresh_status()

    def progress(self, message, percent=None):
        self.progress_label.setText(message)

        if percent is not None:
            bounded_percent = max(
                0,
                min(100, int(percent))
            )
            self.progress_bar.setValue(bounded_percent)

            if bounded_percent >= 90:
                self.cancel_button.setEnabled(False)

        QApplication.processEvents()

    def cancel_process(self):
        if self.processing_feedback is None:
            return

        self.cancel_button.setEnabled(False)
        self.progress_label.setText(
            "Canceling safely..."
        )
        self.processing_feedback.cancel()
        QApplication.processEvents()

    def _set_processing_state(self, running):
        self.run_button.setEnabled(not running)
        self.cancel_button.setEnabled(running)
        self.close_button.setEnabled(not running)
        self.dwg_browse.setEnabled(not running)
        self.output_browse.setEnabled(not running)
        self.dwg_path.setEnabled(not running)
        self.output_path.setEnabled(not running)
        self.boundary_combo.setEnabled(not running)
        self.source_crs.setEnabled(not running)
        self.mapping_count.setEnabled(not running)
        self.activation_button.setEnabled(not running)
        self.guide_button.setEnabled(not running)

        for row in self.mapping_rows:
            row["field"].setEnabled(not running)
            row["layer"].setEnabled(not running)

    def closeEvent(self, event):
        if self.processing_feedback is not None:
            self.cancel_process()
            event.ignore()
            return

        super().closeEvent(event)

    def validate_inputs(self):
        dwg_path = self.dwg_path.text().strip()
        output_path = (
            self.output_path.text().strip()
        )
        boundary_layer = (
            self.boundary_combo
            .currentText()
            .strip()
        )

        if not dwg_path:
            raise ValueError(
                "Select an Input DXF File."
            )

        if not dwg_path.lower().endswith(".dxf"):
            raise ValueError(
                "ParcelForge QGIS accepts DXF files only."
            )

        if not os.path.isfile(dwg_path):
            raise ValueError(
                "The selected DXF file does not exist."
            )

        if not boundary_layer:
            raise ValueError(
                "Select a Boundary Line Layer."
            )

        if not output_path:
            raise ValueError(
                "Select an Output Polygon Layer."
            )

        if not output_path.lower().endswith((".gpkg", ".shp")):
            raise ValueError(
                "Output must use the .gpkg or .shp extension."
            )

        try:
            ensure_new_output(output_path)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc

        if not self.source_crs.crs().isValid():
            raise ValueError(
                "Select the actual CRS of the DXF coordinates. This assigns "
                "a CRS; it does not transform coordinates."
            )
        mappings = []

        for index in range(
                self.mapping_count.value()):

            row = self.mapping_rows[index]
            field_name = (
                row["field"].text().strip()
            )
            text_layer = (
                row["layer"]
                .currentText()
                .strip()
            )

            if not field_name:
                raise ValueError(
                    "Enter Output Field Name for "
                    "Attribute Mapping {0}."
                    .format(index + 1)
                )

            if not text_layer:
                raise ValueError(
                    "Select Source Text Layer for "
                    "Attribute Mapping {0}."
                    .format(index + 1)
                )

            mappings.append((
                field_name,
                text_layer
            ))

        return (
            dwg_path,
            boundary_layer,
            mappings,
            output_path
        )

    @single_run
    def run_process(self):
        # Every new processing run starts visibly from zero, including the
        # input-validation and active-license check stages.
        self.progress_bar.setValue(0)
        self.progress_label.setText(
            "0% — Preparing ParcelForge..."
        )
        QApplication.processEvents()

        try:
            (
                dwg_path,
                boundary_layer,
                mappings,
                output_path
            ) = self.validate_inputs()

        except ValueError as exc:
            self.progress_bar.setValue(0)
            self.progress_label.setText(
                "0% — Correct the input settings before running."
            )
            QMessageBox.warning(
                self,
                "ParcelForge",
                str(exc)
            )
            return

        mode, message = (
            license_manager.access_status(
                refresh_online=True
            )
        )

        self.refresh_status()

        if mode == "inactive":
            self.progress_bar.setValue(0)
            self.progress_label.setText(
                "0% — Activation is required before processing."
            )
            QMessageBox.warning(
                self,
                "ParcelForge Activation",
                message
            )
            self.open_activation()
            return

        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.processing_feedback = ResponsiveProcessingFeedback()
        self._set_processing_state(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText(
            "Starting ParcelForge..."
        )

        try:
            result = (
                cad_reader
                .build_parcel_attributes(
                    dwg_path,
                    boundary_layer,
                    mappings,
                    output_path,
                    self.progress,
                    source_crs=self.source_crs.crs(),
                    feedback=self.processing_feedback
                )
            )

            license_manager.record_success(mode)
            self.refresh_status()

            output_layer = QgsVectorLayer(
                output_path,
                os.path.splitext(
                    os.path.basename(output_path)
                )[0],
                "ogr"
            )

            if output_layer.isValid():
                QgsProject.instance().addMapLayer(
                    output_layer
                )

            summary = (
                "ParcelForge completed successfully.\n\n"
                "Polygons: {0}\n"
                "Labels read: {1}\n"
                "Labels mapped: {2}\n"
                "Labels outside polygons: {3}\n"
                "Polygons with multiple unique values: {4}\n"
                "Output: {5}"
            ).format(
                result["polygon_count"],
                result["labels_read"],
                result["labels_mapped"],
                result["labels_outside"],
                result["multi_value_polygons"],
                result["output_path"]
            )

            self.progress_label.setText(
                "Completed successfully."
            )
            self.progress_bar.setValue(100)

            if (
                    result["labels_outside"] > 0
                    or result["multi_value_polygons"] > 0):
                QMessageBox.warning(
                    self,
                    "ParcelForge — Completed with warnings",
                    summary
                )

            else:
                QMessageBox.information(
                    self,
                    "ParcelForge",
                    summary
                )

        except cad_reader.ParcelForgeCanceled as exc:
            self.progress_label.setText(
                "Canceled. No output was written."
            )
            self.progress_bar.setValue(0)
            QMessageBox.information(
                self,
                "ParcelForge",
                str(exc)
            )

        except Exception as exc:
            self.progress_label.setText(
                "Process failed."
            )
            QMessageBox.critical(
                self,
                "ParcelForge",
                str(exc)
            )

        finally:
            self.processing_feedback = None
            self._set_processing_state(False)
            QApplication.restoreOverrideCursor()
