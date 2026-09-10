import os
import sys
import unittest
import json
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from server import get_or_create_vapid_keys, save_subscription, remove_subscription, load_subscriptions

class TestPushAPI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.subs_file = os.path.join(self.tmp_dir.name, 'subscriptions.json')
        self.keys_file = os.path.join(self.tmp_dir.name, 'vapid_keys.json')

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_vapid_key_format(self):
        pub_key, priv_pem = get_or_create_vapid_keys(filepath=self.keys_file)
        self.assertIsInstance(pub_key, str)
        self.assertGreater(len(pub_key), 60)
        self.assertIn("BEGIN PRIVATE KEY", priv_pem)

    def test_subscription_lifecycle(self):
        sub_sample = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/sample-token-123",
            "keys": {
                "p256dh": "mock-p256dh",
                "auth": "mock-auth"
            }
        }
        # Save subscription
        save_subscription(sub_sample, filepath=self.subs_file)
        subs = load_subscriptions(filepath=self.subs_file)
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["endpoint"], sub_sample["endpoint"])

        # Deduplicate
        save_subscription(sub_sample, filepath=self.subs_file)
        subs = load_subscriptions(filepath=self.subs_file)
        self.assertEqual(len(subs), 1)

        # Remove subscription
        remove_subscription(sub_sample["endpoint"], filepath=self.subs_file)
        subs = load_subscriptions(filepath=self.subs_file)
        self.assertEqual(len(subs), 0)

    def test_vapid_keys_from_root_file(self):
        pub_key, priv_pem = get_or_create_vapid_keys()
        self.assertEqual(pub_key, "BLFNMmvUZn_pHYtqPDWirwKYTkbgoJOdH5JsCbWKOthZvtNth617DFzZ3WG1yYJyz4IgzVOPvcyZeKEYlmezI0I")
        self.assertIn("BEGIN PRIVATE KEY", priv_pem)

if __name__ == '__main__':
    unittest.main()
