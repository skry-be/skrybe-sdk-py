import unittest
from skrybe_sdk import SkrybeSDK
from skrybe_sdk.exceptions import ValidationException

class TestSkrybeSDK(unittest.TestCase):
    def test_init(self):
        sdk = SkrybeSDK(api_key="test")
        self.assertEqual(sdk.api_key, "test")


class TestSendTransactional(unittest.TestCase):
    def setUp(self):
        self.sdk = SkrybeSDK(api_key="test")

    def test_validates_missing_to_email(self):
        with self.assertRaises(ValidationException):
            self.sdk.send_transactional({
                'subject': 'Test',
                'htmlBody': '<p>Test</p>'
            })

    def test_validates_missing_subject(self):
        with self.assertRaises(ValidationException):
            self.sdk.send_transactional({
                'toEmail': 'user@example.com',
                'htmlBody': '<p>Test</p>'
            })

    def test_validates_missing_body(self):
        with self.assertRaises(ValidationException):
            self.sdk.send_transactional({
                'toEmail': 'user@example.com',
                'subject': 'Test'
            })

    def test_validates_invalid_to_email(self):
        with self.assertRaises(ValidationException):
            self.sdk.send_transactional({
                'toEmail': 'invalid-email',
                'subject': 'Test',
                'htmlBody': '<p>Test</p>'
            })

    def test_validates_invalid_from_email(self):
        with self.assertRaises(ValidationException):
            self.sdk.send_transactional({
                'toEmail': 'user@example.com',
                'subject': 'Test',
                'htmlBody': '<p>Test</p>',
                'fromEmail': 'invalid-email'
            })

    def test_accepts_html_body_only(self):
        # Should not raise - valid options with htmlBody only
        try:
            self.sdk._validate_transactional_options({
                'toEmail': 'user@example.com',
                'subject': 'Test',
                'htmlBody': '<p>Test</p>'
            })
        except ValidationException:
            self.fail("Should accept htmlBody without plainBody")

    def test_accepts_plain_body_only(self):
        # Should not raise - valid options with plainBody only
        try:
            self.sdk._validate_transactional_options({
                'toEmail': 'user@example.com',
                'subject': 'Test',
                'plainBody': 'Test'
            })
        except ValidationException:
            self.fail("Should accept plainBody without htmlBody")


if __name__ == "__main__":
    unittest.main()
