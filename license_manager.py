# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""License state and HTTPS activation for ParcelForge."""

import datetime
import hashlib
import json
import os
import platform
import socket
import sys
import uuid
import webbrowser
from urllib.parse import urlencode

from .license_network import request_json

try:
    import winreg
except ImportError:
    winreg = None


PRODUCT_NAME = "ParcelForge"
PRODUCT_CODE = "PARFOR"
FIXED_CODE = "EIN"
APPLICATION_TYPE = "QGIS"
VERSION = "26.1.0"
TRIAL_LIMIT = 2

BASE_URL = "https://aktivasi.ruangspasial.my.id"
REQUEST_URL = BASE_URL + "/request"
USER_GUIDE_URL = BASE_URL + "/help/parcelforge-qgis"

ACTIVATION_ENDPOINTS = [
    BASE_URL + "/api/license/validate",
]

STATUS_ENDPOINTS = [
    BASE_URL + "/api/license/status",
]

SIGNATURE_KEY = "RUANGSPASIAL-PARCELFORGE-PARFOR-EIN-QGIS-V1"


def _machine_guid():
    if winreg is None:
        return ""

    paths = [
        r"SOFTWARE\Microsoft\Cryptography",
        r"SOFTWARE\WOW6432Node\Microsoft\Cryptography",  # pragma: allowlist secret
    ]

    for path in paths:
        try:
            access = winreg.KEY_READ | getattr(
                winreg,
                "KEY_WOW64_64KEY",
                0
            )
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                path,
                0,
                access
            ) as key:
                value, _ = winreg.QueryValueEx(
                    key,
                    "MachineGuid"
                )
                return str(value).strip()
        except (AttributeError, OSError):
            path = ""

    return ""


def device_id():
    parts = [
        platform.system(),
        platform.release(),
        platform.machine(),
        socket.gethostname(),
        str(uuid.getnode()),
        _machine_guid(),
    ]
    raw = "|".join(
        str(value).strip().upper()
        for value in parts
    )
    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest().upper()[:32]


def _state_folder():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser(
            "~/.local/share"
        )
    return os.path.join(
        base,
        "RuangSpasial",
        "LicenseHub",
        "PARCELFORGE_QGIS_PARFOR_EIN"
    )


def _state_path():
    return os.path.join(
        _state_folder(),
        "license.json"
    )


def _default_state():
    return {
        "product": PRODUCT_NAME,
        "product_code": PRODUCT_CODE,
        "fixed_code": FIXED_CODE,
        "application": APPLICATION_TYPE,
        "version": VERSION,
        "device_id": device_id(),
        "status": "trial",
        "trial_used": 0,
        "activation_code": "",
        "token": str(),
        "last_check": "",
        "message": "",
    }


def _signature_payload(state):
    keys = [
        "product",
        "product_code",
        "fixed_code",
        "application",
        "device_id",
        "status",
        "trial_used",
        "activation_code",
        "token",
    ]
    payload = {
        key: state.get(key, "")
        for key in keys
    }
    payload["trial_used"] = int(
        payload.get("trial_used", 0) or 0
    )
    return payload


def _signature(state):
    raw = json.dumps(
        _signature_payload(state),
        sort_keys=True,
        separators=(",", ":")
    )
    raw += "|" + SIGNATURE_KEY
    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest().upper()


def save_state(state):
    os.makedirs(
        _state_folder(),
        exist_ok=True
    )
    state.update({
        "product": PRODUCT_NAME,
        "product_code": PRODUCT_CODE,
        "fixed_code": FIXED_CODE,
        "application": APPLICATION_TYPE,
        "version": VERSION,
        "device_id": device_id(),
    })
    state["signature"] = _signature(state)

    temp_path = _state_path() + ".tmp"
    with open(
        temp_path,
        "w",
        encoding="utf-8"
    ) as stream:
        json.dump(
            state,
            stream,
            indent=2,
            sort_keys=True
        )
    os.replace(temp_path, _state_path())


def load_state():
    state = _default_state()

    if not os.path.isfile(_state_path()):
        return state

    try:
        with open(
            _state_path(),
            "r",
            encoding="utf-8"
        ) as stream:
            loaded = json.load(stream)

        saved_signature = str(
            loaded.pop("signature", "")
        ).upper()

        if loaded.get("device_id") != device_id():
            state["status"] = "inactive"
            state["trial_used"] = TRIAL_LIMIT
            state["message"] = (
                "The saved license belongs to another device."
            )
            return state

        if saved_signature != _signature(loaded):
            state["status"] = "unknown"
            state["trial_used"] = int(
                loaded.get("trial_used", 0) or 0
            )
            state["activation_code"] = str(
                loaded.get("activation_code", "")
            )
            state["token"] = str(
                loaded.get("token", "")
            )
            state["message"] = (
                "The local license requires online validation."
            )
            return state

        state.update(loaded)
        return state

    except Exception:
        state["status"] = "unknown"
        state["message"] = (
            "The local license could not be read."
        )
        return state


def trial_remaining(state=None):
    state = state or load_state()
    return max(
        0,
        TRIAL_LIMIT - int(
            state.get("trial_used", 0) or 0
        )
    )


def _identity_payload():
    return {
        "product": PRODUCT_NAME,
        "product_name": PRODUCT_NAME,
        "plugin": PRODUCT_CODE,
        "plugin_code": PRODUCT_CODE,
        "product_code": PRODUCT_CODE,
        "fixed_code": FIXED_CODE,
        "application": APPLICATION_TYPE,
        "app_type": APPLICATION_TYPE,
        "version": VERSION,
        "device_id": device_id(),
        "machine_id": device_id(),
        "device_name": socket.gethostname(),
    }


def _request(
    endpoint,
    payload,
    method="POST",
    form=False
):
    if form:
        raise ValueError("Form-encoded license requests are disabled.")
    response, error = request_json(
        method,
        endpoint,
        payload,
        timeout=12,
        user_agent="ParcelForge-QGIS/" + VERSION,
    )
    if response is None:
        raise RuntimeError(error or "License Hub returned no response.")
    if not isinstance(response, dict):
        raise RuntimeError("License Hub returned an invalid response.")
    return response


def _nested_dicts(value):
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            if isinstance(nested, (dict, list)):
                yield from _nested_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _nested_dicts(nested)


def _status_from_response(response):
    for current in _nested_dicts(response):
        for key in [
            "active",
            "valid",
            "is_active",
            "activated",
        ]:
            if key in current:
                value = current[key]
                if value is True:
                    return "active"
                if value is False:
                    return "inactive"

        value = str(
            current.get("status")
            or current.get("license_status")
            or current.get("activation_status")
            or ""
        ).strip().lower()

        if value in {
            "active",
            "activated",
            "approved",
            "valid",
        }:
            return "active"

        if value in {
            "inactive",
            "blocked",
            "expired",
            "revoked",
            "invalid",
            "deleted",
        }:
            return "inactive"

        if current.get("success") is True:
            return "active"
        if current.get("success") is False:
            return "inactive"

        message = str(
            current.get("message")
            or current.get("detail")
            or ""
        ).lower()

        if any(
            phrase in message
            for phrase in [
                "aktivasi berhasil",
                "lisensi aktif",
                "activation successful",
                "license active",
            ]
        ):
            return "active"

        if any(
            phrase in message
            for phrase in [
                "tidak aktif",
                "diblokir",
                "inactive",
                "blocked",
                "expired",
            ]
        ):
            return "inactive"

    return ""


def _message(response, fallback):
    for current in _nested_dicts(response):
        for key in [
            "message",
            "detail",
            "description",
            "reason",
            "error",
        ]:
            if current.get(key):
                return str(current[key])
    return fallback


def _try_endpoints(endpoints, payloads):
    errors = []

    for endpoint in endpoints:
        for payload in payloads:
            for method, form in [("POST", False)]:
                try:
                    response = _request(
                        endpoint,
                        payload,
                        method,
                        form
                    )
                    status = _status_from_response(
                        response
                    )
                    if status:
                        return (
                            response,
                            endpoint,
                            method
                        )
                except Exception as exc:
                    errors.append(str(exc))

    return (
        None,
        "",
        errors[-1] if errors else ""
    )


def activate(code):
    code = str(code or "").strip().upper()

    if not code:
        return False, "Enter an Activation Code."

    common = _identity_payload()
    payloads = []

    for field in [
        "activation_code",
        "license_key",
        "code",
        "key",
    ]:
        payload = dict(common)
        payload[field] = code
        payloads.append(payload)

    response, endpoint, transport = _try_endpoints(
        ACTIVATION_ENDPOINTS,
        payloads
    )

    if response is None:
        return (
            False,
            "The License Hub could not confirm the activation."
        )

    if _status_from_response(response) != "active":
        return (
            False,
            _message(
                response,
                "The activation code is not active for this device."
            )
        )

    state = load_state()
    state["status"] = "active"
    state["activation_code"] = code
    state["last_check"] = (
        datetime.datetime.utcnow()
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    state["message"] = (
        "Activation successful. ParcelForge is now Active."
    )
    save_state(state)

    return True, state["message"]


def refresh():
    state = load_state()
    common = _identity_payload()
    payloads = [dict(common)]

    if state.get("activation_code"):
        for field in [
            "activation_code",
            "license_key",
            "code",
        ]:
            payload = dict(common)
            payload[field] = state[
                "activation_code"
            ]
            payloads.append(payload)

    response, endpoint, transport = _try_endpoints(
        STATUS_ENDPOINTS,
        payloads
    )

    if response is None:
        return None, (
            "The License Hub could not be reached."
        )

    status = _status_from_response(response)

    if status == "active":
        state["status"] = "active"
        state["last_check"] = (
            datetime.datetime.utcnow()
            .strftime("%Y-%m-%dT%H:%M:%SZ")
        )
        state["message"] = (
            "License synchronized successfully."
        )
        save_state(state)
        return True, state["message"]

    if status == "inactive":
        state["status"] = "inactive"
        state["message"] = _message(
            response,
            "The license is inactive."
        )
        save_state(state)
        return False, state["message"]

    return None, _message(
        response,
        "The server returned an unrecognized status."
    )


def access_status(refresh_online=False):
    state = load_state()

    if refresh_online:
        result, message = refresh()

        if result is True:
            return "active", message

        if result is False:
            refreshed_state = load_state()
            if refreshed_state.get("activation_code"):
                return "inactive", message
            remaining = trial_remaining(
                refreshed_state
            )

            if remaining > 0:
                return "trial", (
                    "Trial runs remaining: {0}."
                    .format(remaining)
                )

            return "inactive", message

        if result is None and state.get("status") == "active":
            return "inactive", (
                message
                or "The active license could not be verified online."
            )

    if state.get("status") == "active":
        return "active", "License status is active."

    remaining = trial_remaining(state)

    if remaining > 0:
        return (
            "trial",
            "Trial runs remaining: {0}."
            .format(remaining)
        )

    return (
        "inactive",
        state.get("message")
        or "Trial expired. Activate ParcelForge."
    )


def record_success(mode):
    if mode != "trial":
        return

    state = load_state()
    state["trial_used"] = min(
        TRIAL_LIMIT,
        int(state.get("trial_used", 0) or 0) + 1
    )

    if state["trial_used"] >= TRIAL_LIMIT:
        state["status"] = "inactive"
        state["message"] = (
            "Trial expired. Activate ParcelForge."
        )
    else:
        state["status"] = "trial"

    save_state(state)


def status_info(refresh_online=False):
    """
    Return a stable status snapshot for the user interface.

    Returns:
        mode: active, trial, or inactive
        short_text: compact text suitable for a small status pill
        detail: full explanatory text for tooltip/messages
        remaining: remaining successful trial runs
    """
    mode, message = access_status(
        refresh_online
    )
    remaining = trial_remaining()

    if mode == "active":
        return {
            "mode": "active",
            "short_text": "Active",
            "detail": message or "ParcelForge license is active.",
            "remaining": remaining,
        }

    if mode == "trial":
        return {
            "mode": "trial",
            "short_text": "Trial • {0} left".format(
                remaining
            ),
            "detail": (
                "Trial mode — {0} successful run(s) remaining."
                .format(remaining)
            ),
            "remaining": remaining,
        }

    return {
        "mode": "inactive",
        "short_text": "Inactive",
        "detail": (
            message
            or "ParcelForge is inactive. Activate the plugin to continue."
        ),
        "remaining": 0,
    }


def status_text():
    return status_info(False)["short_text"]


def request_url():
    query = urlencode(
        _identity_payload()
    )
    return REQUEST_URL + "?" + query


def open_request_page():
    webbrowser.open(request_url())


def open_user_guide():
    webbrowser.open(USER_GUIDE_URL)
