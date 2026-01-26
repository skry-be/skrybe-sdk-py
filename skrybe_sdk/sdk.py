import time
import json
import requests
from .exceptions import SkrybeException, ValidationException

class SkrybeSDK:
    DEFAULT_BASE_URL = "https://dashboard.skry.be"
    MIN_REQUEST_INTERVAL = 0.1  # 100ms

    def __init__(self, api_key, base_url=None):
        self.api_key = api_key
        self.base_url = base_url or self.DEFAULT_BASE_URL
        self.last_request_time = 0
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "SkrybeSDK-Python/1.0"
        })

    def _create_form_data(self, data):
        form_data = {"api_key": self.api_key}
        for key, value in data.items():
            if value is not None:
                if isinstance(value, (list, dict)):
                    form_data[key] = json.dumps(value)
                else:
                    form_data[key] = value
        return form_data

    def _handle_rate_limit(self):
        now = time.time()
        time_since_last = now - self.last_request_time
        if time_since_last < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - time_since_last)
        self.last_request_time = time.time()

    def _make_request(self, endpoint, data):
        self._handle_rate_limit()
        url = self.base_url + endpoint
        try:
            response = self.session.post(url, data=self._create_form_data(data))
            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return response.text
        except requests.RequestException as e:
            raise SkrybeException(str(e)) from e

    def _make_json_request(self, endpoint, data):
        self._handle_rate_limit()
        url = self.base_url + endpoint
        payload = {"api_key": self.api_key}
        for key, value in data.items():
            if value is not None:
                payload[key] = value
        try:
            response = requests.post(
                url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "SkrybeSDK-Python/1.0"
                }
            )
            response.raise_for_status()
            try:
                return response.json()
            except Exception:
                return response.text
        except requests.RequestException as e:
            raise SkrybeException(str(e)) from e

    def _validate_email_options(self, options):
        required = ['fromName', 'fromEmail', 'subject', 'htmlText']
        errors = []
        for field in required:
            if not options.get(field):
                errors.append(f"Field '{field}' is required")
        if 'fromEmail' in options and '@' not in options['fromEmail']:
            raise ValidationException({'fromEmail': 'Invalid email format'})
        if 'to' in options:
            for email in options['to']:
                if '@' not in email:
                    raise ValidationException({'to': f"Invalid email format: {email}"})
        if errors:
            raise ValidationException(errors)

    def _validate_campaign_options(self, options):
        required = ['fromName', 'fromEmail', 'title', 'subject', 'htmlText']
        errors = []
        for field in required:
            if not options.get(field):
                errors.append(f"Field '{field}' is required")
        if 'fromEmail' in options and '@' not in options['fromEmail']:
            raise ValidationException({'fromEmail': 'Invalid email format'})
        if errors:
            raise ValidationException(errors)

    def _validate_transactional_options(self, options):
        errors = []
        if not options.get('toEmail'):
            errors.append("Field 'toEmail' is required")
        if not options.get('subject'):
            errors.append("Field 'subject' is required")
        if not options.get('htmlBody') and not options.get('plainBody'):
            errors.append("Either 'htmlBody' or 'plainBody' is required")
        if options.get('toEmail') and '@' not in options['toEmail']:
            errors.append("Field 'toEmail' has invalid email format")
        if options.get('fromEmail') and '@' not in options['fromEmail']:
            errors.append("Field 'fromEmail' has invalid email format")
        if options.get('replyTo') and '@' not in options['replyTo']:
            errors.append("Field 'replyTo' has invalid email format")
        if errors:
            raise ValidationException(errors)

    def send_email(self, options):
        self._validate_email_options(options)
        return self._make_request('/api/emails/send.php', {
            'from_name': options['fromName'],
            'from_email': options['fromEmail'],
            'reply_to': options.get('replyTo'),
            'subject': options['subject'],
            'html_text': options['htmlText'],
            'plain_text': options.get('plainText'),
            'to': options.get('to'),
            'recipient-variables': options.get('recipientVariables'),
            'list_ids': ','.join(options['listIds']) if options.get('listIds') else None,
            'query_string': options.get('queryString'),
            'track_opens': options.get('trackOpens'),
            'track_clicks': options.get('trackClicks'),
            'schedule_date_time': options.get('scheduleDateTime'),
            'schedule_timezone': options.get('scheduleTimezone'),
        })

    def send_transactional(self, options):
        """
        Send a transactional email (OTP, password reset, alerts, etc.).

        Unlike send_email, this delivers immediately without queuing or scheduling.

        Args:
            options: dict with the following keys:
                - toEmail (required): Recipient email address (single email only)
                - subject (required): Email subject
                - htmlBody: HTML version of the email (required if plainBody not provided)
                - plainBody: Plain text version (required if htmlBody not provided)
                - fromName (optional): Override brand's 'From name'
                - fromEmail (optional): Override brand's 'From email'
                - replyTo (optional): Override brand's 'Reply to' email

        Returns:
            dict: API response with 'status' and 'message' keys
        """
        self._validate_transactional_options(options)
        return self._make_json_request('/api/emails/send-transactional.php', {
            'to_email': options['toEmail'],
            'subject': options['subject'],
            'html_body': options.get('htmlBody'),
            'plain_body': options.get('plainBody'),
            'from_name': options.get('fromName'),
            'from_email': options.get('fromEmail'),
            'reply_to': options.get('replyTo'),
        })

    def create_campaign(self, options):
        self._validate_campaign_options(options)
        return self._make_request('/api/campaigns/create.php', {
            'from_name': options['fromName'],
            'from_email': options['fromEmail'],
            'reply_to': options.get('replyTo'),
            'title': options['title'],
            'subject': options['subject'],
            'html_text': options['htmlText'],
            'plain_text': options.get('plainText'),
            'list_ids': options.get('listIds'),
            'segment_ids': options.get('segmentIds'),
            'exclude_list_ids': options.get('excludeListIds'),
            'exclude_segments_ids': options.get('excludeSegmentIds'),
            'query_string': options.get('queryString'),
            'track_opens': options.get('trackOpens'),
            'track_clicks': options.get('trackClicks'),
            'send_campaign': options.get('sendCampaign'),
            'schedule_date_time': options.get('scheduleDateTime'),
            'schedule_timezone': options.get('scheduleTimezone'),
        })

    def get_lists(self, include_hidden=False):
        return self._make_request('/api/lists/get-lists.php', {
            'include_hidden': 'yes' if include_hidden else 'no'
        })

    def get_campaigns(self, options=None):
        options = options or {}
        return self._make_request('/api/campaigns/get-campaigns.php', {
            'page': options.get('page', 1),
            'limit': options.get('limit', 10),
            'status': options.get('status')
        })

    def get_subscribers(self, list_id, options=None):
        options = options or {}
        return self._make_request('/api/subscribers/get-subscribers.php', {
            'list_id': list_id,
            'page': options.get('page', 1),
            'limit': options.get('limit', 10),
            'status': options.get('status')
        })

    def add_subscriber(self, list_id, subscriber_data):
        data = {'list_id': list_id}
        data.update(subscriber_data)
        return self._make_request('/api/subscribers/add.php', data)
