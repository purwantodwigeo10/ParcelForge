# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""Dialogs and duplicate-analysis workflow for Find Duplicate."""

import os
import shutil
import tempfile
import traceback

from qgis.PyQt.QtCore import Qt, QUrl, QVariant
from qgis.PyQt.QtGui import QDesktopServices, QPixmap
from qgis.PyQt.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
)
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsMapLayerType,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
    QgsWkbTypes,
)

from .licensehub_fd_qgis import (
    FIXED_CODE,
    LicenseManager,
    PRODUCT_CODE,
    PRODUCT_NAME,
    TRIAL_LIMIT,
)
from .duplicate_utils import format_xy, unique_dbf_name, value_key
from .shapefile_utils import commit_shapefile


HELP_URL = (
    'https://aktivasi.ruangspasial.my.id/help/find-duplicate-qgis'
)
DIALOG_STYLE = (
    'QDialog { background-color: white; } '
    'QGroupBox { background-color: white; border: 1px solid #d9d9d9; '
    'margin-top: 8px; } '
    'QGroupBox::title { subcontrol-origin: margin; left: 10px; '
    'padding: 0 3px; background-color: white; } '
    'QTextEdit, QLabel { background-color: white; }'
)


class ActivationDialog(QDialog):
    """Display and manage the RUANG SPASIAL license state."""

    def __init__(self, license_manager, parent=None):
        super(ActivationDialog, self).__init__(parent)
        self.lm = license_manager
        self.setWindowTitle('License Activation')
        window_flags = (
            self.windowFlags()
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowFlags(window_flags)
        self.setSizeGripEnabled(True)
        self.resize(700, 190)
        self.setStyleSheet(DIALOG_STYLE)
        self._build_ui()
        self.refresh_status(True)

    def _build_ui(self):
        main = QVBoxLayout(self)
        grid = QGridLayout()

        self.lbl_status = QLabel('-')
        self.txt_device_id = QLineEdit()
        self.txt_device_id.setReadOnly(True)
        self.btn_copy = QPushButton('Copy Device ID')
        self.btn_copy.clicked.connect(self.copy_device_id)
        self.lbl_trial = QLabel('-')
        self.txt_code = QLineEdit()
        self.txt_code.setPlaceholderText(
            'Enter the activation code from License Hub')

        grid.addWidget(QLabel('Activation Status'), 0, 0)
        grid.addWidget(self.lbl_status, 0, 1, 1, 2)
        grid.addWidget(QLabel('Device ID'), 1, 0)
        grid.addWidget(self.txt_device_id, 1, 1)
        grid.addWidget(self.btn_copy, 1, 2)
        grid.addWidget(QLabel('Trial Usage'), 2, 0)
        grid.addWidget(self.lbl_trial, 2, 1, 1, 2)
        grid.addWidget(QLabel('Activation Code'), 3, 0)
        grid.addWidget(self.txt_code, 3, 1, 1, 2)
        main.addLayout(grid)

        row = QHBoxLayout()
        self.btn_request = QPushButton('Submit Request')
        self.btn_request.clicked.connect(self.open_request_page)
        self.btn_activate = QPushButton('Activate')
        self.btn_activate.clicked.connect(self.activate_license)
        self.btn_refresh = QPushButton('Refresh Status')
        self.btn_refresh.clicked.connect(lambda: self.refresh_status(False))
        self.btn_close = QPushButton('Close')
        self.btn_close.clicked.connect(self.accept)
        row.addStretch(1)
        row.addWidget(self.btn_request)
        row.addWidget(self.btn_activate)
        row.addWidget(self.btn_refresh)
        row.addWidget(self.btn_close)
        main.addLayout(row)

    def refresh_status(self, quiet=True):
        self.txt_device_id.setText(self.lm.get_device_id())
        self._display_local_status()
        if quiet:
            return

        ok, message = self.lm.refresh_activation_from_server()
        self.txt_device_id.setText(self.lm.get_device_id())
        self._display_local_status()
        if ok is True:
            QMessageBox.information(
                self,
                PRODUCT_NAME,
                'License status was refreshed from the website.')
        elif ok is False:
            QMessageBox.warning(
                self,
                PRODUCT_NAME,
                message or 'License is not active.')
        else:
            QMessageBox.warning(
                self,
                PRODUCT_NAME,
                message or (
                    'License status could not be confirmed from the '
                    'website.'))

    def _display_local_status(self):
        status = self.lm.status_text()
        self.lbl_status.setText(status)
        remaining = self.lm.trial_remaining()
        self.lbl_trial.setText(
            '%s/%s used, %s remaining' % (
                TRIAL_LIMIT - remaining,
                TRIAL_LIMIT,
                remaining,
            ))
        if status.startswith('Active'):
            color = '#0B7A2A'
        elif status.startswith('Trial'):
            color = '#B35C00'
        elif status.startswith('Expired'):
            color = '#B00020'
        else:
            color = '#7A003C'
        self.lbl_status.setStyleSheet(
            'font-weight:bold;color:%s;' % color)

    def copy_device_id(self):
        QApplication.clipboard().setText(
            self.txt_device_id.text().strip())
        QMessageBox.information(
            self,
            PRODUCT_NAME,
            'Device ID copied successfully.')

    def open_request_page(self):
        try:
            if not self.lm.open_request_url():
                raise RuntimeError(
                    'The browser did not accept the activation URL.')
            QMessageBox.information(
                self,
                PRODUCT_NAME,
                (
                    'The activation request page has been opened. Please '
                    'submit the request with Product Code %s and Fixed '
                    'Code %s.'
                ) % (PRODUCT_CODE, FIXED_CODE))
        except (OSError, RuntimeError) as error:
            QMessageBox.warning(
                self,
                PRODUCT_NAME,
                'Failed to open request page: %s' % error)

    def activate_license(self):
        ok, message = self.lm.activate(self.txt_code.text().strip())
        self.refresh_status(True)
        if ok:
            QMessageBox.information(self, PRODUCT_NAME, message)
            self.accept()
        else:
            QMessageBox.warning(self, PRODUCT_NAME, message)


class FindDuplicateDialog(QDialog):
    """Run duplicate detection on a QGIS vector layer."""

    def __init__(self, iface, parent=None):
        super(FindDuplicateDialog, self).__init__(parent)
        self.iface = iface
        self.lm = LicenseManager()
        self.setWindowTitle('Find Duplicate')
        window_flags = (
            self.windowFlags()
            | Qt.WindowMinimizeButtonHint
            | Qt.WindowMaximizeButtonHint
            | Qt.WindowCloseButtonHint
        )
        self.setWindowFlags(window_flags)
        self.setSizeGripEnabled(True)
        self.resize(900, 720)
        self.setStyleSheet(DIALOG_STYLE)
        self._build_ui()
        self.load_layers()
        self.refresh_license_status()

    def _build_ui(self):
        main = QVBoxLayout(self)
        hero = QGroupBox()
        hero_layout = QHBoxLayout(hero)

        self.lbl_logo = QLabel()
        self.lbl_logo.setStyleSheet('background-color: white;')
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            self.lbl_logo.setPixmap(
                pixmap.scaled(
                    170,
                    170,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation))
        self.lbl_logo.setMinimumWidth(220)
        self.lbl_logo.setAlignment(Qt.AlignCenter)
        hero_layout.addWidget(self.lbl_logo)

        center = QVBoxLayout()
        self.lbl_title = QLabel(
            "<span style='font-size:24px; font-weight:700;'>"
            'Find Duplicate</span>')
        self.lbl_title.setTextFormat(Qt.RichText)
        self.lbl_desc = QLabel(
            'Identify duplicate or unique values in a selected field and '
            'create a documented output Shapefile for data-quality review.')
        self.lbl_desc.setWordWrap(True)
        center.addWidget(self.lbl_title)
        center.addWidget(self.lbl_desc)
        center.addStretch(1)
        hero_layout.addLayout(center, 1)

        right = QVBoxLayout()
        self.lbl_plugin_status = QLabel()
        self.lbl_plugin_status.setTextFormat(Qt.RichText)
        self.lbl_activation = QLabel()
        self.lbl_activation.setTextFormat(Qt.RichText)
        self.btn_manage = QPushButton('Manage Activation')
        self.btn_manage.clicked.connect(self.show_activation_dialog)
        self.btn_help_main = QPushButton('User Guide and Activation')
        self.btn_help_main.clicked.connect(self.open_help_page)
        right.addWidget(self.lbl_plugin_status, 0, Qt.AlignRight)
        right.addWidget(self.lbl_activation, 0, Qt.AlignRight)
        right.addWidget(self.btn_manage, 0, Qt.AlignRight)
        right.addWidget(self.btn_help_main, 0, Qt.AlignRight)
        right.addStretch(1)
        hero_layout.addLayout(right)
        main.addWidget(hero)

        tool_box = QGroupBox('Duplicate Analysis')
        layout = QVBoxLayout(tool_box)
        grid = QGridLayout()

        self.txt_input_file = QLineEdit()
        self.txt_input_file.setPlaceholderText(
            'Optional: browse input data directly from a folder')
        self.txt_input_file.editingFinished.connect(self.on_layer_changed)
        self.btn_input_file = QPushButton('Browse Input...')
        self.btn_input_file.clicked.connect(self.choose_input_file)
        self.cmb_layer = QComboBox()
        self.cmb_layer.currentIndexChanged.connect(self.on_layer_changed)
        self.cmb_field = QComboBox()
        self.lst_select_fields = QListWidget()
        self.lst_select_fields.setMinimumHeight(170)
        self.txt_output = QLineEdit()
        self.btn_output = QPushButton('Save Output...')
        self.btn_output.clicked.connect(self.choose_output)

        grid.addWidget(QLabel('Input Data From Folder'), 0, 0)
        grid.addWidget(self.txt_input_file, 0, 1)
        grid.addWidget(self.btn_input_file, 0, 2)
        grid.addWidget(QLabel('Input Layer (Loaded in QGIS)'), 1, 0)
        grid.addWidget(self.cmb_layer, 1, 1, 1, 2)
        grid.addWidget(QLabel('Field to Check for Duplicates'), 2, 0)
        grid.addWidget(self.cmb_field, 2, 1, 1, 2)
        layout.addLayout(grid)

        fields_box = QGroupBox('Fields to Keep (Optional)')
        fields_layout = QVBoxLayout(fields_box)
        fields_button_row = QHBoxLayout()
        self.btn_select_all = QPushButton('Select All')
        self.btn_select_all.clicked.connect(self.select_all_fields)
        self.btn_unselect_all = QPushButton('Unselect All')
        self.btn_unselect_all.clicked.connect(self.unselect_all_fields)
        fields_button_row.addWidget(self.btn_select_all)
        fields_button_row.addWidget(self.btn_unselect_all)
        fields_button_row.addStretch(1)
        fields_layout.addLayout(fields_button_row)
        fields_layout.addWidget(self.lst_select_fields)
        layout.addWidget(fields_box)

        output_grid = QGridLayout()
        output_grid.addWidget(QLabel('Output Shapefile (.shp)'), 0, 0)
        output_grid.addWidget(self.txt_output, 0, 1)
        output_grid.addWidget(self.btn_output, 0, 2)
        layout.addLayout(output_grid)

        progress_row = QHBoxLayout()
        self.lbl_progress = QLabel('Ready')
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFormat('%p%')
        progress_row.addWidget(self.lbl_progress)
        progress_row.addWidget(self.progress, 1)
        layout.addLayout(progress_row)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(260)
        layout.addWidget(self.log)
        main.addWidget(tool_box)

        bottom = QHBoxLayout()
        self.btn_run = QPushButton('Run Tool')
        self.btn_run.clicked.connect(self.run_tool)
        self.btn_cancel = QPushButton('Cancel')
        self.btn_cancel.clicked.connect(self.close)
        bottom.addStretch(1)
        bottom.addWidget(self.btn_run)
        bottom.addWidget(self.btn_cancel)
        main.addLayout(bottom)

    def open_help_page(self):
        if not QDesktopServices.openUrl(QUrl(HELP_URL)):
            QMessageBox.warning(
                self,
                PRODUCT_NAME,
                'The help page could not be opened in the web browser.')

    def show_activation_dialog(self):
        dialog = ActivationDialog(self.lm, self)
        dialog.exec_()
        self.refresh_license_status()

    def refresh_license_status(self):
        self.lbl_plugin_status.setText(
            "<b><span style='color:#0B7A2A;'>"
            'Plugin Status: Ready</span></b>')
        status = self.lm.status_text()
        if status.startswith('Active'):
            state = 'Active'
            color = '#0B7A2A'
        elif status.startswith('Trial'):
            state = 'Trial'
            color = '#B35C00'
        elif status.startswith('Expired'):
            state = 'Expired'
            color = '#B00020'
        else:
            state = 'Deactivated'
            color = '#7A003C'
        self.lbl_activation.setText(
            "<b><span style='color:%s;'>Activation: %s</span></b>" % (
                color,
                state,
            ))

    def log_msg(self, message):
        self.log.append(str(message))

    def set_progress(self, value, message):
        """Update the live analysis progress without starting a new thread."""
        value = max(0, min(100, int(value)))
        self.progress.setValue(value)
        self.lbl_progress.setText(str(message))
        QApplication.processEvents()

    def load_layers(self):
        self.cmb_layer.clear()
        for layer in QgsProject.instance().mapLayers().values():
            if layer.type() == QgsMapLayerType.VectorLayer:
                self.cmb_layer.addItem(layer.name(), layer.id())
        self.on_layer_changed()

    @staticmethod
    def _open_vector_from_path(path):
        if not path or not os.path.exists(path):
            return None
        layer = QgsVectorLayer(path, os.path.basename(path), 'ogr')
        return layer if layer.isValid() else None

    def current_layer(self):
        input_path = self.txt_input_file.text().strip()
        if input_path:
            return self._open_vector_from_path(input_path)
        layer_id = self.cmb_layer.currentData()
        if not layer_id:
            return None
        return QgsProject.instance().mapLayer(layer_id)

    def on_layer_changed(self):
        self.cmb_field.clear()
        self.lst_select_fields.clear()
        layer = self.current_layer()
        if layer is None or not layer.isValid():
            return
        for field in layer.fields():
            name = field.name()
            self.cmb_field.addItem(name)
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.lst_select_fields.addItem(item)

    def choose_input_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            'Select input data from folder',
            '',
            'Vector Data (*.shp *.gpkg *.geojson *.json *.kml *.tab);;'
            'All Files (*.*)')
        if not path:
            return
        layer = self._open_vector_from_path(path)
        if layer is None:
            QMessageBox.warning(
                self,
                PRODUCT_NAME,
                'The selected input cannot be opened as a vector layer.')
            return
        self.txt_input_file.setText(path)
        self.on_layer_changed()
        self.log_msg('Input selected from folder: %s' % path)

    def choose_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            'Save output Shapefile',
            '',
            'Shapefile (*.shp)')
        if path:
            base, extension = os.path.splitext(path)
            if extension.lower() != '.shp':
                path = base + '.shp' if extension else path + '.shp'
            self.txt_output.setText(path)

    def select_all_fields(self):
        for index in range(self.lst_select_fields.count()):
            self.lst_select_fields.item(index).setCheckState(Qt.Checked)

    def unselect_all_fields(self):
        for index in range(self.lst_select_fields.count()):
            self.lst_select_fields.item(index).setCheckState(Qt.Unchecked)

    def selected_fields(self):
        names = []
        for index in range(self.lst_select_fields.count()):
            item = self.lst_select_fields.item(index)
            if item.checkState() == Qt.Checked:
                names.append(item.text())
        return names

    def run_tool(self, checked=False):
        del checked
        if getattr(self, '_operation_running', False):
            return
        self._operation_running = True
        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.set_progress(0, 'Checking license and input...')
        try:
            can_run, message = self.lm.can_run()
            if not can_run:
                self.refresh_license_status()
                self.set_progress(0, 'Unable to start')
                QMessageBox.warning(self, PRODUCT_NAME, message)
                return

            using_trial = not self.lm.is_activated_local()
            self.set_progress(10, 'License check completed')
            output = self._process()
            if using_trial:
                self.set_progress(97, 'Recording successful trial run...')
                self.lm.consume_trial_for_run()
                self.log_msg(
                    'Trial run completed. Remaining trial: %s of %s.' % (
                        self.lm.trial_remaining(),
                        TRIAL_LIMIT,
                    ))
            self.set_progress(100, 'Analysis completed')
            self.log_msg('Process completed. Output: %s' % output)
            QMessageBox.information(
                self,
                PRODUCT_NAME,
                'Process completed.\n\nOutput: %s' % output)
            self.refresh_license_status()
        except Exception as error:
            self.lbl_progress.setText('Analysis failed')
            self.log_msg(
                'ERROR: %s\n%s' % (error, traceback.format_exc()))
            QMessageBox.critical(
                self,
                PRODUCT_NAME,
                'Failed to run tool:\n%s' % error)
        finally:
            self.btn_run.setEnabled(True)
            self.btn_cancel.setEnabled(True)
            self._operation_running = False

    def _process(self):
        self.set_progress(15, 'Validating analysis settings...')
        layer = self.current_layer()
        if layer is None or not layer.isValid():
            raise RuntimeError('Please select a valid input vector layer.')

        duplicate_field = self.cmb_field.currentText().strip()
        if not duplicate_field:
            raise RuntimeError(
                'Please select a field to check for duplicates.')
        if layer.fields().indexOf(duplicate_field) < 0:
            raise RuntimeError(
                'The duplicate-check field no longer exists in the input.')

        requested_output = self.txt_output.text().strip()
        if not requested_output:
            raise RuntimeError('Please choose an output Shapefile path.')
        output_path = os.path.abspath(requested_output)
        if not output_path.lower().endswith('.shp'):
            raise RuntimeError('Output must be a Shapefile (.shp).')
        output_path = os.path.splitext(output_path)[0] + '.shp'
        output_directory = os.path.dirname(output_path)
        if not os.path.isdir(output_directory):
            raise RuntimeError(
                'The output folder does not exist: %s' % output_directory)

        keep_names = [duplicate_field]
        all_names = [field.name() for field in layer.fields()]
        for name in self.selected_fields():
            if name in all_names and name not in keep_names:
                keep_names.append(name)
        input_indexes = [layer.fields().indexOf(name) for name in keep_names]

        self.set_progress(22, 'Reading input features...')
        features = []
        total_source = max(1, int(layer.featureCount()))
        update_every = max(1, total_source // 100)
        for index, feature in enumerate(layer.getFeatures(), 1):
            features.append(feature)
            if index == total_source or index % update_every == 0:
                self.set_progress(
                    22 + int(10 * min(index, total_source) / total_source),
                    'Reading feature %s of %s...' % (
                        index,
                        total_source,
                    ))
        if not features:
            raise RuntimeError(
                'The selected input layer contains no features.')
        value_locations = self._collect_value_locations(
            features,
            duplicate_field)

        self.set_progress(52, 'Preparing output fields...')
        memory_layer = self._create_memory_layer(layer)
        provider = memory_layer.dataProvider()
        output_fields = self._build_output_fields(layer, input_indexes)
        if not provider.addAttributes(output_fields):
            raise RuntimeError('Failed to create the output field structure.')
        memory_layer.updateFields()

        output_features = self._build_output_features(
            features,
            duplicate_field,
            input_indexes,
            value_locations,
            memory_layer.fields())
        add_result = provider.addFeatures(output_features)
        add_ok = add_result[0] if isinstance(add_result, tuple) else add_result
        if not add_ok:
            raise RuntimeError('Failed to create output features.')
        memory_layer.updateExtents()

        self.set_progress(82, 'Writing output Shapefile...')
        self._write_output(memory_layer, output_path, len(output_features))
        self.set_progress(94, 'Opening and validating the final output...')
        output_layer = QgsVectorLayer(
            output_path,
            os.path.basename(output_path),
            'ogr')
        if not output_layer.isValid():
            raise RuntimeError(
                'The output was written but could not be reopened by QGIS.')
        QgsProject.instance().addMapLayer(output_layer)
        self.set_progress(96, 'Final output added to QGIS')
        return output_path

    @staticmethod
    def _feature_xy(feature):
        geometry = feature.geometry()
        if geometry is None or geometry.isEmpty():
            return None
        try:
            point = geometry.centroid().asPoint()
            return (float(point.x()), float(point.y()))
        except Exception:
            return None

    def _collect_value_locations(self, features, duplicate_field):
        locations = {}
        total = max(1, len(features))
        update_every = max(1, total // 100)
        for index, feature in enumerate(features, 1):
            key = value_key(feature[duplicate_field])
            locations.setdefault(key, []).append(
                self._feature_xy(feature))
            if index == total or index % update_every == 0:
                self.set_progress(
                    32 + int(18 * index / total),
                    'Counting duplicate values %s of %s...' % (
                        index,
                        total,
                    ))
        return locations

    def _build_output_fields(self, layer, input_indexes):
        output_fields = []
        used_names = set()
        for index in input_indexes:
            output_field = QgsField(layer.fields()[index])
            output_field.setName(
                unique_dbf_name(output_field.name(), used_names))
            output_fields.append(output_field)

        analysis_fields = (
            QgsField('NOTES', QVariant.String, len=50),
            QgsField('FREQUENCY', QVariant.Int),
            QgsField('LOCATIONS', QVariant.String, len=254),
            QgsField('DETAIL', QVariant.String, len=254),
        )
        for field in analysis_fields:
            field.setName(unique_dbf_name(field.name(), used_names))
            output_fields.append(field)
        return output_fields

    @staticmethod
    def _create_memory_layer(source_layer):
        geometry_name = QgsWkbTypes.displayString(source_layer.wkbType())
        crs = source_layer.crs()
        uri = geometry_name
        if crs.isValid() and crs.authid():
            uri += '?crs=' + crs.authid()
        memory_layer = QgsVectorLayer(
            uri,
            'FindDuplicateOutput',
            'memory')
        if not memory_layer.isValid():
            raise RuntimeError(
                'Failed to create the temporary output layer.')
        if crs.isValid():
            memory_layer.setCrs(crs)
        return memory_layer

    def _build_output_features(
            self,
            features,
            duplicate_field,
            input_indexes,
            value_locations,
            output_fields):
        output_features = []
        total = max(1, len(features))
        update_every = max(1, total // 100)
        for index, feature in enumerate(features, 1):
            value = feature[duplicate_field]
            locations = value_locations.get(value_key(value), [])
            frequency = len(locations)
            is_duplicate = frequency > 1
            notes = (
                'DUPLICATE IDENTIFIED'
                if is_duplicate
                else 'UNIQUE IDENTIFIED')
            formatted_locations = [
                format_xy(location)
                for location in locations
                if location is not None
            ]
            locations_text = ' & '.join(formatted_locations)
            value_text = 'NULL' if value is None else str(value)
            if is_duplicate:
                detail = (
                    'The %s value %s is identified as DUPLICATE at '
                    'locations %s' % (
                        duplicate_field,
                        value_text,
                        locations_text,
                    ))
            else:
                detail = (
                    'The %s value %s is identified as UNIQUE at location '
                    '%s' % (
                        duplicate_field,
                        value_text,
                        format_xy(self._feature_xy(feature)),
                    ))

            output_feature = QgsFeature(output_fields)
            output_feature.setGeometry(feature.geometry())
            attributes = [feature[index] for index in input_indexes]
            attributes.extend((
                notes,
                frequency,
                locations_text[:254],
                detail[:254],
            ))
            output_feature.setAttributes(attributes)
            output_features.append(output_feature)
            if index == total or index % update_every == 0:
                self.set_progress(
                    56 + int(22 * index / total),
                    'Classifying feature %s of %s...' % (
                        index,
                        total,
                    ))
        return output_features

    def _write_output(self, memory_layer, output_path, expected_count):
        output_directory = os.path.dirname(output_path)
        temporary_directory = tempfile.mkdtemp(
            prefix='find_duplicate_',
            dir=output_directory)
        temporary_path = os.path.join(
            temporary_directory,
            os.path.basename(output_path))
        try:
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = 'ESRI Shapefile'
            options.fileEncoding = 'UTF-8'
            result = QgsVectorFileWriter.writeAsVectorFormatV2(
                memory_layer,
                temporary_path,
                QgsProject.instance().transformContext(),
                options)
            error_code = result[0] if isinstance(result, tuple) else result
            if error_code != QgsVectorFileWriter.NoError:
                raise RuntimeError(
                    'QGIS failed to save the output Shapefile.')

            self.set_progress(88, 'Validating temporary output...')
            check_layer = QgsVectorLayer(
                temporary_path,
                'FindDuplicateValidation',
                'ogr')
            if not check_layer.isValid():
                raise RuntimeError(
                    'The new Shapefile failed the QGIS validation check.')
            if check_layer.featureCount() != expected_count:
                raise RuntimeError(
                    'The output feature count does not match the input.')
            del check_layer

            self.set_progress(92, 'Finalizing output Shapefile...')
            commit_shapefile(temporary_path, output_path)
        finally:
            shutil.rmtree(temporary_directory, ignore_errors=True)
