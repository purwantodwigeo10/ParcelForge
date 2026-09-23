# SPDX-License-Identifier: GPL-3.0-or-later
"""Explicit denial anywhere in the response takes precedence over success."""


DENIED_STATES = {
    "inactive",
    "expired",
    "revoked",
    "blocked",
    "invalid",
    "rejected",
    "disabled",
    "deleted",
    "deactivated",
    "not_found",
    "pending",
    "waiting",
    "nonactive",
    "nonaktif",
    "tidak_aktif",
    "kadaluarsa",
    "kedaluwarsa",
}

STATUS_KEYS = {
    "status",
    "license_status",
    "activation_status",
    "state",
    "approval_status",
    "request_status",
}

DENIAL_MESSAGES = (
    "not active",
    "not valid",
    "inactive",
    "revoked",
    "blocked",
    "expired",
    "tidak aktif",
    "tidak berhasil",
    "aktivasi gagal",
    "activation failed",
    "license deleted",
)


def has_denial(value):
    if isinstance(value, list):
        return any(has_denial(item) for item in value)

    if not isinstance(value, dict):
        return False

    for key, flag in value.items():
        key = str(key).strip().lower()
        normalized = (
            str(flag)
            .strip()
            .lower()
            .replace(" ", "_")
            .replace("-", "_")
        )

        if key in STATUS_KEYS and normalized in DENIED_STATES:
            return True

        if (
                key in {"active", "valid", "is_active", "activated", "approved"}
                and normalized in {"false", "0", "no"}):
            return True

        if (
                key in {"revoked", "blocked", "disabled", "deleted", "expired"}
                and normalized in {"true", "1", "yes"}):
            return True

        if key in {"message", "detail", "msg", "pesan"}:
            message = str(flag).lower()

            if any(phrase in message for phrase in DENIAL_MESSAGES):
                return True

        if isinstance(flag, (dict, list)) and has_denial(flag):
            return True

    return False
