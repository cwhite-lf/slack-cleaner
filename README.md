# Slack Cleaner

This script helps clean up Slack channels by archiving inactive channels or channels that only contain users with specified email domains.

## Requirements

- Python 3.x
- `slack_sdk` library
- `python-dotenv` library

You can also use a `Pipfile` to manage the dependencies. First, ensure you have `pipenv` installed:

```bash
pip install pipenv
```

Then, you can install the required libraries using the `Pipfile`:

```bash
pipenv install
```

## Usage

```
python slack-cleaner.py <api_token> [--email-domains EMAIL_DOMAINS [EMAIL_DOMAINS ...]] [--days DAYS] [--live] [--csv]
```

### Arguments
- `api_token`: Slack API token (if not specified in .env).
- `--email-domains domain.com` (optional): List of email domains to check.
- `--days ###` (optional): Archive channels with no messages in the last number of days.
- `--live` (optional): Run in live mode (not a dry run).
- `--verbose` (optional): Run in verbose mode.
- `--csv filename` (optional): Export the list of archived channels to a CSV file.

### Example
`python slack-cleaner.py xoxb-1234-56789-abcdef --email-domains example.com anotherdomain.com --days 30 --live --csv`

## Obtaining a Slack API Token
To use this script, you need a Slack API token. Follow these steps to obtain one:

1. Go to the Slack API page.
1. Click on "Create an App".
1. Choose "From scratch".
1. Enter an app name and select your workspace.
1. Click "Create App".
1. Go to "OAuth & Permissions" in the sidebar.
1. Scroll down to "Scopes" and add the following   scopes:
    1. channels:read
    1. channels:history
    1. channels:manage
    1. users:read
1. Click "Install App to Workspace".
1. Click "Allow" to grant the necessary permissions.
1. Copy the "Bot User OAuth Token" and use it as the `api_token` when running the script.

## License
This project is licensed under the MIT License.