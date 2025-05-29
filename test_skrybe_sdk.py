import unittest
from skrybe_sdk import SkrybeSDK

class TestSkrybeSDK(unittest.TestCase):
    def test_init(self):
        sdk = SkrybeSDK(api_key="test")
        self.assertEqual(sdk.api_key, "test")

if __name__ == "__main__":
    unittest.main()
