# Skrybe SDK for Django (Python)

A Python package providing a Django-compatible SDK for the Skrybe API, inspired by the official PHP and TypeScript SDKs.

## Features
- Send emails and create campaigns via Skrybe API
- List and manage subscribers and campaigns
- Pythonic API, ready for Django integration

## Installation

```bash
pip install .
```

## Usage

```python
from skrybe_sdk import SkrybeSDK
sdk = SkrybeSDK(api_key="YOUR_API_KEY")
response = sdk.get_lists()
print(response)
```

## Development
- Main code in `skrybe_sdk/`
- Tests in `tests/`

## License
MIT
