import os
import sys
import tempfile
import unittest
from unittest.mock import patch


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_TEMP = tempfile.TemporaryDirectory(prefix="hub-owner-test-")
_ENV_KEYS = (
    "JP_DATA_DIR",
    "JP_CONFIG",
    "JP_ADMIN_PASSWORD",
    "JP_ADMIN_EMAIL",
    "JP_ADMIN_PHONE",
    "JP_FIREBASE_API_KEY",
    "JP_FIREBASE_AUTH_DOMAIN",
    "JP_FIREBASE_PROJECT_ID",
    "JP_FIREBASE_APP_ID",
)
_ORIGINAL_ENV = {key: os.environ.get(key) for key in _ENV_KEYS}
os.environ["JP_DATA_DIR"] = os.path.join(_TEMP.name, "data")
os.environ["JP_CONFIG"] = os.path.join(_TEMP.name, "config.ini")
for _key in _ENV_KEYS[2:]:
    os.environ.pop(_key, None)

sys.path.insert(0, PROJECT_ROOT)
import app as hub

for _key, _value in _ORIGINAL_ENV.items():
    if _value is None:
        os.environ.pop(_key, None)
    else:
        os.environ[_key] = _value


class FirstAdminOwnerTests(unittest.TestCase):
    def test_owner_contact_is_required_before_first_account(self):
        with patch.dict(os.environ, {"JP_ADMIN_EMAIL": "", "JP_ADMIN_PHONE": ""}):
            self.assertFalse(hub._owner_ok("email", "anyone@example.com"))
            self.assertFalse(hub._owner_ok("sms", "+919876543210"))

    def test_only_matching_configured_owner_contact_is_accepted(self):
        with patch.dict(
            os.environ,
            {"JP_ADMIN_EMAIL": "owner@example.com", "JP_ADMIN_PHONE": "+919876543210"},
        ):
            self.assertTrue(hub._owner_ok("email", "owner@example.com"))
            self.assertFalse(hub._owner_ok("email", "other@example.com"))
            self.assertTrue(hub._owner_ok("sms", "+919876543210"))
            self.assertFalse(hub._owner_ok("sms", "+919876543211"))


if __name__ == "__main__":
    unittest.main()
