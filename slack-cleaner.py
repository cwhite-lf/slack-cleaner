import sys
import time
import argparse
import csv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv
import os
import requests

# Load environment variables from .env file
load_dotenv()

# Initialize the Slack client
client = None

# Cache for user info and channel membership
user_info_cache = {}
channel_members_cache = {}

# Function to handle Slack API requests with rate limiting
def slack_api_request(func, *args, **kwargs):
    while True:
        try:
            response = func(*args, **kwargs)
            return response
        except SlackApiError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get('Retry-After', 1))
                print(f"Rate limited. Retrying after {retry_after} seconds.")
                time.sleep(retry_after)
            else:
                raise e

# Function to get channels
def get_channels():
    try:
        response = slack_api_request(client.conversations_list, limit=999, exclude_archived=True)
        return response['channels']
    except SlackApiError as e:
        print(f"Error fetching channels: {e.response['error']}")
        return []

# Function to get channel users with caching
def get_channel_users(channel_id):
    if channel_id in channel_members_cache:
        return channel_members_cache[channel_id]
    try:
        response = slack_api_request(client.conversations_members, channel=channel_id)
        channel_members_cache[channel_id] = response['members']
        return response['members']
    except SlackApiError as e:
        print(f"Error fetching channel members: {e.response['error']}")
        return []

# Function to get user info with caching
def get_user_info(user_id):
    if user_id in user_info_cache:
        return user_info_cache[user_id]
    try:
        response = slack_api_request(client.users_info, user=user_id)
        user_info_cache[user_id] = response['user']
        return response['user']
    except SlackApiError as e:
        print(f"Error fetching user info: {e.response['error']}")
        return None

# Function to join a channel
def join_channel(channel_id, channel_name=None):
    try:
        slack_api_request(client.conversations_join, channel=channel_id)
        print(f"Joined channel #{channel_name}")
    except SlackApiError as e:
        print(f"Error joining channel #{channel_name}: {e.response['error']}")

# Function to check if a channel is archived
def is_channel_archived(channel_id):
    try:
        response = slack_api_request(client.conversations_info, channel=channel_id)
        return response['channel']['is_archived']
    except SlackApiError as e:
        print(f"Error checking if channel is archived: {e.response['error']}")
        return False

# Function to fetch channel history with optional join
def fetch_channel_history(channel_id, join_channels, channel_name):
    try:
        response = slack_api_request(client.conversations_history, channel=channel_id)
        return response['messages']
    except SlackApiError as e:
        if e.response['error'] == 'not_in_channel':
            if join_channels:
                if not is_channel_archived(channel_id):
                    join_channel(channel_id, channel_name)
                return retry_fetch_channel_history(channel_id, channel_name)
            else:
                return prompt_and_join_channel(channel_id, channel_name)
        else:
            print(f"Error fetching channel history: {e.response['error']}")
            return []

# Helper function to retry fetching channel history after joining
def retry_fetch_channel_history(channel_id, channel_name):
    try:
        response = slack_api_request(client.conversations_history, channel=channel_id)
        return response['messages']
    except SlackApiError as e:
        print(f"Error fetching channel #{channel_name} history after joining: {e.response['error']}")
        return []

# Helper function to prompt user and join channel if confirmed
def prompt_and_join_channel(channel_id, channel_name):
    user_input = input(f"The Slack Cleaner app does not have access to #{channel_name} channel, would you like to join? [Nya] ").strip().lower()
    if user_input in ['y', 'yes']:
        if not is_channel_archived(channel_id):
            join_channel(channel_id, channel_name)
        return retry_fetch_channel_history(channel_id, channel_name)
    else:
        print(f"Skipping channel #{channel_id}")
        return []

# Function to get channel history
def get_channel_history(channel_id, join_channels, channel_name):
    return fetch_channel_history(channel_id, join_channels, channel_name)

# Function to archive a channel
def archive_channel(channel_id, dry_run=True, channel_name=None, reason=None):
    if dry_run:
        print(f"Dry run: Would archive channel {channel_name} for reason: {reason}")
    else:
        try:
            client.conversations_archive(channel=channel_id)
            print(f"Archived channel {channel_name} for reason: {reason}")
        except SlackApiError as e:
            print(f"Error archiving channel: {e.response['error']}")

# Main function to clean up Slack instance
def clean_up_slack(email_domains, dry_run=True, days=None, join_channels=False, csv_filename=None):
    csv_writer = None
    if csv_filename:
        csv_file = open(csv_filename, 'w', newline='')
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['Channel ID', 'Channel Name', 'Reason'])

    channels = get_channels()
    for channel in channels:
        channel_id = channel['id']
        channel_name = channel['name']
        already_archived = channel['is_archived']
        try:
            history = get_channel_history(channel_id, join_channels, channel_name)
            # Check if channel is inactive
            if days is not None:
                if history:
                    last_message_time = float(history[1]['ts'])
                    if args.verbose:
                        print (f"Second-to-last message in channel {channel_name} was {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_message_time))}")
                    if time.time() - last_message_time > days * 24 * 60 * 60:
                        reason = f"Most recent message is {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_message_time))}"
                        archive_channel(channel_id, dry_run, channel_name, reason)
                        already_archived = True
                        if csv_writer:
                            csv_writer.writerow([channel_id, channel_name, reason])

                        continue
            
            # Check if channel only contains users with specified email domains
            users = get_channel_users(channel_id)
            if users and not already_archived:
                if args.verbose:
                    print(f"Checking channel #{channel_name} with {len(users)} users")
                all_users_match = True
                for user_id in users:
                    user_info = get_user_info(user_id)
                    if user_info:
                        email = user_info['profile'].get('email', '')
                        if not any(email.endswith(domain) for domain in email_domains):
                            all_users_match = False
                            break
                if args.verbose:
                    print(f"Channel #{channel_name} has users from {' '.join(email_domains)}: {all_users_match}")
                if all_users_match:
                    reason = "No users in specified domains"
                    archive_channel(channel_id, dry_run, channel_name, reason, csv_writer)
                    if csv_writer:
                            csv_writer.writerow([channel_id, channel_name, reason])

        except Exception as e:
            print(f"Error processing channel #{channel_name}: {e}")

    if csv_filename:
        csv_file.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up Slack channels.")
    parser.add_argument("api_token", nargs="?", default=os.getenv("SLACK_API_TOKEN"), help="Slack API token (optional if SLACK_API_TOKEN is set in .env)")
    parser.add_argument("--email-domains", nargs="+", default=["example.com", "anotherdomain.com"], help="List of email domains to check")
    parser.add_argument("--days", type=int, help="Archive channels with no messages in the last number of days")
    parser.add_argument("--live", action="store_true", help="Run in live mode (not a dry run)")
    parser.add_argument("--join-channels", action="store_true", help="Join channels if not already a member")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--csv", type=str, help="Output archived channels to a CSV file")

    args = parser.parse_args()

    if not args.api_token:
        parser.print_help()
        sys.exit(1)
    
    if os.getenv("SLACK_API_TOKEN") is not None:
        print("Using SLACK_API_TOKEN from .env file")

    if args.days is not None:
        print(f"Archiving channels with no messages in the last {args.days} days")

    if args.email_domains:
        print(f"Checking for channels with users from {args.email_domains}")

    if args.live:
        print("Running in live mode")
    else:
        print("DRY RUN: Use --live to run in live mode")

    if args.join_channels:
        print("Will join channels if not already a member")

    if args.csv:
        print(f"Outputting archived channels to {args.csv}")

    client = WebClient(token=args.api_token)
    dry_run = not args.live
    clean_up_slack(args.email_domains, dry_run, args.days, args.join_channels, args.csv)