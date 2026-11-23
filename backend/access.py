"""Optional protection for a copy that is reachable from the internet.

Both switches are OFF by default (local use needs neither):

* SHEM_PASSWORD=<text>  every request must send HTTP Basic auth with this
                        password (any user name). The browser shows its own
                        login dialog.
* SHEM_READ_ONLY=1      visitors can look at everything and use the
                        calculators, but cannot change rooms, devices,
                        readings or settings.
"""

import base64
import binascii
import hmac
import os

# Requests that only compute something and are allowed in read-only mode.
READ_ONLY_ALLOWED_POSTS = {"/api/explain", "/api/optimize", "/api/brief"}


def password():
    return os.environ.get("SHEM_PASSWORD") or None


def read_only():
    return os.environ.get("SHEM_READ_ONLY", "").strip().lower() in ("1", "true", "yes")


def authorised(header):
    """True if no password is configured or the Basic auth header matches it."""
    expected = password()
    if expected is None:
        return True
    if not header or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:].strip()).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    _, _, given = decoded.partition(":")
    return hmac.compare_digest(given.encode("utf-8"), expected.encode("utf-8"))


def blocked_by_read_only(method, path):
    if not read_only() or method in ("GET", "HEAD"):
        return False
    return path.rstrip("/") not in READ_ONLY_ALLOWED_POSTS


READ_ONLY_MESSAGE = ("This copy of the app is read-only: you can explore everything, "
                     "but changes are disabled.")
