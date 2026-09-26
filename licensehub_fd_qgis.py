# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""RUANG SPASIAL License Hub integration for Find Duplicate.

All remote license operations use HTTPS through QGIS' network manager so QGIS
proxy and certificate settings are respected.
"""

import hashlib
import json
import os
import platform
import sys
import uuid
import webbrowser

try:
    import winreg
except ImportError:  # Non-Windows platforms
    winreg = None

from urllib.parse import urlencode, urlparse

try:
    from qgis.PyQt.QtCore import QByteArray, QEventLoop, QSysInfo, QTimer, QUrl
    from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest
    from qgis.core import QgsNetworkAccessManager
except ImportError:  # Allows safe checks outside QGIS
    QByteArray = None
    QEventLoop = None
    QSysInfo = None
    QTimer = None
    QUrl = None
    QNetworkReply = None
    QNetworkRequest = None
    QgsNetworkAccessManager = None


BASE_URL = "https://aktivasi.ruangspasial.my.id"
REQUEST_URL = BASE_URL + "/request"
VALIDATE_URL = BASE_URL + "/api/license/validate"
STATUS_URL = BASE_URL + "/api/license/status"

PRODUCT_CODE = "FIDU"
FIXED_CODE = "SW"
PRODUCT_NAME = "Find Duplicate"
PLUGIN_VERSION = "26.1.0"
TRIAL_LIMIT = 2
LICENSE_FOLDER = "FIND_DUPLICATE_QGIS_FIDU_SW"


class LicenseManager(object):
    """Store local trial state and validate activated licenses."""

    def __init__(self):
        self.app_dir = os.path.join(
            self._application_data_root(),
            "RuangSpasial",
            "LicenseHub",
            LICENSE_FOLDER,
        )
        os.makedirs(self.app_dir, exist_ok=True)
        self.license_file = os.path.join(self.app_dir, "license.json")
        self.seed_file = os.path.join(self.app_dir, "device_seed")

    @staticmethod
    def _application_data_root():
        """Return a writable per-user data directory on supported platforms."""
        if os.name == "nt":
            return os.environ.get("APPDATA") or os.path.expanduser("~")
        if sys.platform == "darwin":
            return os.path.expanduser("~/Library/Application Support")
        return os.environ.get(
            "XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    @staticmethod
    def _read_machine_guid():
        """Preserve the existing Windows Device ID source for compatibility."""
        if winreg is None:
            return ""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
            )
            try:
                value, _ = winreg.QueryValueEx(key, "MachineGuid")
            finally:
                winreg.CloseKey(key)
            return str(value).strip()
        except (OSError, ValueError):
            return ""

    @staticmethod
    def _read_qt_machine_id():
        if QSysInfo is None:
            return ""
        try:
            value = QSysInfo.machineUniqueId()
            return bytes(value).decode("utf-8", errors="ignore").strip()
        except (AttributeError, TypeError, ValueError):
            return ""

    @staticmethod
    def _read_linux_machine_id():
        for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    value = handle.read().strip()
                if value:
                    return value
            except (OSError, UnicodeError):
                continue
        return ""

    def _read_or_create_local_seed(self):
        """Use a persistent random fallback instead of a shared constant ID."""
        try:
            with open(self.seed_file, "r", encoding="ascii") as handle:
                value = handle.read().strip()
            if value:
                return value
        except (OSError, UnicodeError):
            value = ""

        value = uuid.uuid4().hex
        temporary = self.seed_file + ".tmp"
        try:
            with open(temporary, "w", encoding="ascii") as handle:
                handle.write(value)
            os.replace(temporary, self.seed_file)
            try:
                os.chmod(self.seed_file, 0o600)
            except OSError:
                return value
        except OSError:
            try:
                if os.path.exists(temporary):
                    os.remove(temporary)
            except OSError:
                temporary = ""
            return "%s|%s" % (platform.node(), uuid.getnode())
        return value

    def get_device_id(self):
        # Windows continues to use MachineGuid, so existing licenses remain
        # valid.
        raw = (
            self._read_machine_guid()
            or self._read_qt_machine_id()
            or self._read_linux_machine_id()
            or self._read_or_create_local_seed()
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest().upper()[:32]

    def _default_state(self):
        return {
            "product_code": PRODUCT_CODE,
            "fixed_code": FIXED_CODE,
            "activated": False,
            "activation_code": "",
            "trial_used": 0,
            "last_status": "TRIAL",
            "device_id": self.get_device_id(),
        }

    def load_state(self):
        if not os.path.exists(self.license_file):
            return self._default_state()
        try:
            with open(self.license_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                data = self._default_state()
        except (OSError, ValueError, TypeError):
            data = self._default_state()

        for key, value in self._default_state().items():
            data.setdefault(key, value)
        data["product_code"] = PRODUCT_CODE
        data["fixed_code"] = FIXED_CODE
        data["device_id"] = self.get_device_id()
        return data

    def save_state(self, state):
        state["product_code"] = PRODUCT_CODE
        state["fixed_code"] = FIXED_CODE
        state["device_id"] = self.get_device_id()
        temporary = self.license_file + ".tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, sort_keys=True)
            os.replace(temporary, self.license_file)
            try:
                os.chmod(self.license_file, 0o600)
            except OSError:
                return
        except OSError:
            try:
                if os.path.exists(temporary):
                    os.remove(temporary)
            except OSError:
                temporary = ""
            raise

    def trial_remaining(self):
        state = self.load_state()
        try:
            used = int(state.get("trial_used", 0))
        except (TypeError, ValueError):
            used = 0
        return max(0, TRIAL_LIMIT - used)

    def is_activated_local(self):
        state = self.load_state()
        return (
            bool(state.get("activated", False))
            and bool(str(state.get("activation_code", "")).strip())
            and str(state.get("product_code", "")).upper() == PRODUCT_CODE
            and str(state.get("fixed_code", "")).upper() == FIXED_CODE
        )

    def status_text(self):
        state = self.load_state()
        if self.is_activated_local():
            return "Active"
        status = str(state.get("last_status", "")).upper()
        if status in ("BLOCKED", "DEACTIVATED", "REVOKED", "INACTIVE_SERVER"):
            return "Deactivated - License is not active"
        remaining = self.trial_remaining()
        if remaining > 0:
            return "Trial - %s of %s uses remaining" % (remaining, TRIAL_LIMIT)
        return "Expired - Trial limit reached"

    def request_url(self):
        params = {
            "device_id": self.get_device_id(),
            "plugin": PRODUCT_CODE,
            "product_code": PRODUCT_CODE,
            "fixed_code": FIXED_CODE,
            "product_name": PRODUCT_NAME,
        }
        return REQUEST_URL + "?" + urlencode(params)

    def open_request_url(self):
        return webbrowser.open(self.request_url())

    @staticmethod
    def _secure_url(url):
        if urlparse is None:
            return False
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        return (
            parsed.scheme.lower() == "https"
            and parsed.hostname == "aktivasi.ruangspasial.my.id"
        )

    @staticmethod
    def _decode_response(raw):
        try:
            value = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def _post_json_qgis(self, url, payload, timeout):
        request = QNetworkRequest(QUrl(url))
        request.setHeader(
            QNetworkRequest.ContentTypeHeader,
            "application/json")
        request.setRawHeader(
            QByteArray(b"Accept"),
            QByteArray(b"application/json"))
        request.setRawHeader(
            QByteArray(b"User-Agent"),
            QByteArray(
                ("FindDuplicate/%s QGIS" %
                 PLUGIN_VERSION).encode("ascii")),
        )

        reply = QgsNetworkAccessManager.instance().post(
            request,
            QByteArray(json.dumps(payload).encode("utf-8")),
        )
        event_loop = QEventLoop()
        timer = QTimer()
        timer.setSingleShot(True)
        reply.finished.connect(event_loop.quit)
        timer.timeout.connect(event_loop.quit)
        timer.start(max(1, int(timeout * 1000)))
        event_loop.exec_()

        if not reply.isFinished():
            reply.abort()
            reply.deleteLater()
            return None, "License Hub did not respond before the timeout."

        raw = bytes(reply.readAll()).decode("utf-8", errors="replace")
        error_code = reply.error()
        error_text = reply.errorString()
        reply.deleteLater()
        parsed = self._decode_response(raw)
        if parsed is not None:
            return parsed, None
        if error_code != QNetworkReply.NoError:
            return None, "License Hub request failed: %s" % error_text
        return None, "License Hub returned an invalid response."

    def _post_json(self, url, payload, timeout=10):
        if not self._secure_url(url):
            return None, (
                "The license request was blocked because its endpoint is not "
                "HTTPS."
            )
        if QgsNetworkAccessManager is None:
            return None, "QGIS network manager is not available."
        return self._post_json_qgis(url, payload, timeout)

    @staticmethod
    def _status_from_response(data):
        if not isinstance(data, dict):
            return None, "Invalid License Hub response."

        status = str(
            data.get("status")
            or data.get("license_status")
            or data.get("message")
            or ""
        ).strip().upper()
        message = data.get("message") or ""
        if status == "PENDING":
            return False, message or "License request is still pending."
        if (
            data.get("active") is False
            or data.get("approved") is False
            or data.get("valid") is False
            or status
            in (
                "BLOCKED",
                "DEACTIVATED",
                "INACTIVE",
                "REVOKED",
                "REJECTED",
                "EXPIRED",
                "NOT_FOUND",
            )
        ):
            return False, message or "License is not active."
        if (
            data.get("active") is True
            or data.get("approved") is True
            or data.get("valid") is True
            or status in ("ACTIVE", "AKTIF", "APPROVED", "VALID")
        ):
            return True, message or "License active."
        return None, message or "License status could not be verified."

    def _license_payload(self, activation_code):
        return {
            "product": PRODUCT_CODE,
            "product_code": PRODUCT_CODE,
            "fixed_code": FIXED_CODE,
            "product_name": PRODUCT_NAME,
            "plugin": PRODUCT_CODE,
            "tool": PRODUCT_NAME,
            "device_id": self.get_device_id(),
            "activation_code": activation_code,
            "code": activation_code,
        }

    @staticmethod
    def _inactive_state(state, message):
        state["activated"] = False
        upper = str(message).upper()
        if "PENDING" in upper:
            state["last_status"] = "PENDING"
        elif "BLOCK" in upper:
            state["last_status"] = "BLOCKED"
        elif "REVOK" in upper or "DEACTIV" in upper:
            state["last_status"] = "DEACTIVATED"
        else:
            state["last_status"] = "INACTIVE_SERVER"

    def activate(self, activation_code):
        code = str(activation_code or "").strip().upper()
        if not code:
            return False, "Enter the activation code first."

        data, error = self._post_json(
            VALIDATE_URL, self._license_payload(code))
        if data is None:
            return False, error or (
                "Activation could not be verified by License Hub."
            )

        active, message = self._status_from_response(data)
        state = self.load_state()
        state["activation_code"] = code
        if active is True:
            state["activated"] = True
            state["last_status"] = "ACTIVE"
            self.save_state(state)
            return True, message or "Activation successful."
        if active is False:
            self._inactive_state(state, message)
            self.save_state(state)
            return False, message or "License is not active."
        return False, message or "License status could not be verified."

    def refresh_activation_from_server(self):
        state = self.load_state()
        code = str(state.get("activation_code", "")).strip().upper()
        if not code:
            return None, "No activation code is stored locally yet."

        data, error = self._post_json(STATUS_URL, self._license_payload(code))
        if data is None:
            return None, error or "License status could not be confirmed."

        active, message = self._status_from_response(data)
        if active is True:
            state["activated"] = True
            state["last_status"] = "ACTIVE"
            self.save_state(state)
            return True, message or "License active."
        if active is False:
            self._inactive_state(state, message)
            self.save_state(state)
            return False, message or "License is not active."
        return None, message or "License status could not be confirmed."

    def can_run(self):
        if self.is_activated_local():
            active, message = self.refresh_activation_from_server()
            if active is True:
                return True, "License is active."
            return False, message or (
                "The active license could not be verified."
            )
        if self.trial_remaining() > 0:
            return True, "Trial mode. Remaining trial: %s of %s." % (
                self.trial_remaining(),
                TRIAL_LIMIT,
            )
        return False, "Trial has expired. Please activate the license."

    def consume_trial_for_run(self):
        state = self.load_state()
        if state.get("activated", False):
            return True
        try:
            used = int(state.get("trial_used", 0) or 0)
        except (TypeError, ValueError):
            used = 0
        if used >= TRIAL_LIMIT:
            state["last_status"] = "TRIAL_EXPIRED"
            self.save_state(state)
            return False
        state["trial_used"] = used + 1
        state["last_status"] = (
            "TRIAL" if state["trial_used"] < TRIAL_LIMIT else "TRIAL_EXPIRED"
        )
        self.save_state(state)
        return True
