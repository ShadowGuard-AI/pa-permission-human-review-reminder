import argparse
import logging
import schedule
import time
import datetime
import smtplib
from email.mime.text import MIMEText
import os
import re
import json
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants (configurable via CLI or config file later)
# Only the config file default below is ever used. The SMTP and sender
# defaults further down are dead: validate_config requires those keys
# in the file, so a config that omits them fails instead of falling
# back to the values named here.
DEFAULT_CONFIG_FILE = "permission_review_config.json"
DEFAULT_SMTP_SERVER = "localhost"  # Replace with your SMTP server
DEFAULT_SMTP_PORT = 25  # Replace with your SMTP port
DEFAULT_SENDER_EMAIL = "permission_review@example.com"  # Replace with your sender email


def setup_argparse() -> argparse.ArgumentParser:
    """
    Sets up the argument parser for the CLI.

    Returns:
        argparse.ArgumentParser: The argument parser.
    """
    parser = argparse.ArgumentParser(description="Schedule periodic permission reviews and send email notifications.")
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG_FILE,
                        help="Path to the configuration file. Defaults to permission_review_config.json")
    parser.add_argument("-t", "--test-email", action="store_true",
                        help="Send a test email using the configured settings.  Will not schedule reviews.")
    return parser


def load_config(config_file: str) -> Dict:
    """
    Loads the configuration from a JSON file.

    Args:
        config_file: Path to the JSON configuration file.

    Returns:
        dict: The configuration loaded from the file.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        json.JSONDecodeError: If the configuration file is not valid JSON.
    """
    try:
        with open(config_file, "r") as f:
            config = json.load(f)
        logging.info(f"Configuration loaded from {config_file}")
        return config
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_file}")
        raise
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in configuration file: {config_file}. Error: {e}")
        raise


def validate_config(config: Dict) -> None:
    """
    Validates the configuration to ensure required keys and values are present.

    Args:
        config: The configuration dictionary.

    Raises:
        ValueError: If the configuration is invalid.
    """

    required_keys = ["permissions_to_review", "reviewers", "smtp_server", "smtp_port", "sender_email"]

    for key in required_keys:
        if key not in config:
            raise ValueError(f"Missing required configuration key: {key}")

    if not isinstance(config["permissions_to_review"], list):
        raise ValueError("permissions_to_review must be a list of dictionaries.")

    for permission in config["permissions_to_review"]:
        if not isinstance(permission, dict):
            raise ValueError("Each permission entry in permissions_to_review must be a dictionary.")
        required_permission_keys = ["description", "permission_details", "review_schedule"]
        for key in required_permission_keys:
            if key not in permission:
                raise ValueError(f"Missing required key in permission: {key}")
        if not isinstance(permission["permission_details"], dict):
            raise ValueError("permission_details must be a dictionary")
        if not isinstance(permission["review_schedule"], str):
            raise ValueError("review_schedule must be a string")

    if not isinstance(config["reviewers"], list):
        raise ValueError("reviewers must be a list of dictionaries.")

    for reviewer in config["reviewers"]:
        if not isinstance(reviewer, dict):
            raise ValueError("Each reviewer entry in reviewers must be a dictionary.")
        required_reviewer_keys = ["name", "email"]
        for key in required_reviewer_keys:
            if key not in reviewer:
                raise ValueError(f"Missing required key in reviewer: {key}")
        if not isinstance(reviewer["email"], str) or "@" not in reviewer["email"]:
            raise ValueError("Reviewer email must be a valid email address.")

    if not isinstance(config["smtp_server"], str):
        raise ValueError("smtp_server must be a string.")
    try:
        port = int(config["smtp_port"])
        if not (0 < port < 65535):
            raise ValueError("smtp_port must be an integer between 1 and 65535")
    except ValueError:
        raise ValueError("smtp_port must be an integer between 1 and 65535")
    if not isinstance(config["sender_email"], str) or "@" not in config["sender_email"]:
        raise ValueError("Sender email must be a valid email address.")

    # Optional mail transport and review form settings.
    if "smtp_use_tls" in config and not isinstance(config["smtp_use_tls"], bool):
        raise ValueError("smtp_use_tls must be a boolean.")
    for key in ("smtp_username", "smtp_password"):
        if key in config and not isinstance(config[key], str):
            raise ValueError(f"{key} must be a string.")
    if "smtp_username" in config and "smtp_password" not in config:
        raise ValueError("smtp_password is required when smtp_username is set.")
    if "review_form_url" in config and not isinstance(config["review_form_url"], str):
        raise ValueError("review_form_url must be a string.")


def send_email(subject: str, body: str, recipient: str, smtp_server: str, smtp_port: int, sender_email: str, use_tls: bool = False, username: str = None, password: str = None) -> None:
    """
    Sends an email using the specified SMTP settings.

    Args:
        subject: The subject of the email.
        body: The body of the email.
        recipient: The recipient's email address.
        smtp_server: The SMTP server hostname.
        smtp_port: The SMTP server port.
        sender_email: The sender's email address.

    Raises:
        smtplib.SMTPException: If there is an error sending the email.
    """
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender_email
        msg["To"] = recipient

        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if use_tls:
                server.starttls()
            if username:
                server.login(username, password or "")
            server.sendmail(sender_email, recipient, msg.as_string())
        logging.info(f"Email sent successfully to {recipient}")
    except smtplib.SMTPException as e:
        logging.error(f"Error sending email to {recipient}: {e}")
        raise


def create_review_task(permission: Dict, reviewer: Dict, smtp_server: str, smtp_port: int, sender_email: str, use_tls: bool = False, username: str = None, password: str = None, review_form_url: str = None) -> None:
    """
    Creates a review task and sends an email to the reviewer.

    Args:
        permission: A dictionary containing details about the permission to review.
        reviewer: A dictionary containing the reviewer's information.
        smtp_server: The SMTP server hostname.
        smtp_port: The SMTP server port.
        sender_email: The sender's email address.
    """
    subject = f"Permission Review Required: {permission['description']}"
    if review_form_url:
        form_line = f"Review form: {review_form_url}"
    else:
        form_line = "Please use your organization's own review process to record this review."
    body = f"""
    Dear {reviewer['name']},

    A review is required for the following permission:

    Description: {permission['description']}
    Details: {permission['permission_details']}

    Please review this permission and ensure it is still appropriate.

    {form_line}

    Thank you,
    The Permission Review System
    """

    try:
        send_email(subject, body, reviewer["email"], smtp_server, smtp_port, sender_email, use_tls, username, password)
    except Exception as e:
        logging.error(f"Failed to send email for {permission['description']} review to {reviewer['email']}: {e}")


ACCEPTED_SCHEDULE_FORMS = (
    "'every N seconds/minutes/hours/days/weeks', "
    "'daily at HH:MM', or 'weekly on <weekday>' optionally followed by 'at HH:MM'"
)
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_TIME_PATTERN = r"((?:[01][0-9]|2[0-3]):[0-5][0-9])"


def parse_and_schedule(schedule_string: str, job) -> None:
    """
    Schedules one job from a review_schedule string using a narrow parser.

    The config value is data, never code: only the fixed forms listed in
    ACCEPTED_SCHEDULE_FORMS are accepted, and anything else raises
    ValueError. No part of the string is ever evaluated or executed.

    Args:
        schedule_string: The review_schedule value from the config.
        job: The callable to schedule.

    Raises:
        ValueError: If the value matches no accepted form.
    """
    text = " ".join(str(schedule_string).strip().lower().split())

    match = re.fullmatch(r"every ([0-9]+) (second|seconds|minute|minutes|hour|hours|day|days|week|weeks)", text)
    if match:
        interval = int(match.group(1))
        if interval <= 0:
            raise ValueError(f"Invalid review_schedule value: {schedule_string!r}. Interval must be positive. Accepted forms: {ACCEPTED_SCHEDULE_FORMS}")
        unit = match.group(2)
        if not unit.endswith("s"):
            unit += "s"
        getattr(schedule.every(interval), unit).do(job)
        return

    match = re.fullmatch(r"(?:daily|every day) at " + _TIME_PATTERN, text)
    if match:
        schedule.every().day.at(match.group(1)).do(job)
        return

    match = re.fullmatch(r"(?:weekly on|every week on) (" + "|".join(_WEEKDAYS) + r")(?: at " + _TIME_PATTERN + r")?", text)
    if match:
        builder = getattr(schedule.every(), match.group(1))
        if match.group(2):
            builder = builder.at(match.group(2))
        builder.do(job)
        return

    raise ValueError(f"Invalid review_schedule value: {schedule_string!r}. Accepted forms: {ACCEPTED_SCHEDULE_FORMS}")


def schedule_reviews(config: Dict) -> int:
    """
    Schedules the permission reviews based on the configuration.

    Args:
        config: The configuration dictionary.

    Returns:
        The number of jobs that were scheduled. A value that matches no
        accepted form is logged as an error and schedules nothing.
    """
    scheduled = 0
    # The loops form the full cross product: every reviewer is emailed
    # about every permission. The config schema has no way to assign a
    # permission to a specific reviewer, so adding a reviewer adds a
    # copy of every reminder, not just the ones they own.
    for permission in config["permissions_to_review"]:
        for reviewer in config["reviewers"]:
            schedule_string = permission["review_schedule"]

            def job(permission=permission, reviewer=reviewer):
                create_review_task(
                    permission, reviewer,
                    config["smtp_server"], config["smtp_port"], config["sender_email"],
                    config.get("smtp_use_tls", False),
                    config.get("smtp_username"), config.get("smtp_password"),
                    config.get("review_form_url"),
                )

            try:
                parse_and_schedule(schedule_string, job)
                scheduled += 1
                logging.info(f"Scheduled review for {permission['description']} by {reviewer['name']} with schedule: {schedule_string}")
            except ValueError as e:
                logging.error(f"Failed to schedule review for {permission['description']} by {reviewer['name']}: {e}")
            except Exception as e:
                logging.error(f"Failed to schedule review for {permission['description']} by {reviewer['name']} with schedule: {schedule_string}: {e}")
    return scheduled


def send_test_email(smtp_server: str, smtp_port: int, sender_email: str, use_tls: bool = False, username: str = None, password: str = None) -> bool:
    """
    Sends a test email to ensure email settings are correct.

    The test message is sent to the sender address.

    Args:
        smtp_server: The SMTP server hostname.
        smtp_port: The SMTP server port.
        sender_email: The sender's email address.

    Returns:
        True when the test email was sent, False when it failed.
    """
    test_recipient = sender_email  # Send to sender to verify.  Ideally this would be configurable via CLI args.
    subject = "Test Email from Permission Review Tool"
    body = "This is a test email to verify that the email settings are configured correctly."
    try:
        send_email(subject, body, test_recipient, smtp_server, smtp_port, sender_email, use_tls, username, password)
        print("Test email sent successfully. Check your inbox.")  # Added console output for user feedback
        return True
    except Exception as e:
        print(f"Failed to send test email: {e}")  # Added console output for user feedback
        logging.error(f"Failed to send test email: {e}")
        return False


def main():
    """
    Main function to parse arguments, load configuration, and schedule reviews.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    try:
        config = load_config(args.config)
        validate_config(config)

        if args.test_email:
            sent = send_test_email(
                config["smtp_server"], config["smtp_port"], config["sender_email"],
                config.get("smtp_use_tls", False),
                config.get("smtp_username"), config.get("smtp_password"),
            )
            if not sent:
                exit(1)
        else:
            scheduled = schedule_reviews(config)
            if scheduled == 0:
                # Nothing will ever be sent, so the daemon must not sit in
                # its run loop presenting as healthy.
                print("Error: No reviews were scheduled. Check that permissions_to_review and reviewers are not empty and that every review_schedule value uses an accepted form.")
                logging.error("No reviews scheduled; exiting instead of running with zero jobs.")
                exit(1)

            while True:
                schedule.run_pending()
                # The parser above accepts "every N seconds", but this
                # loop only wakes once a minute, so a sub minute
                # schedule can never fire more often than the poll, and
                # it fires late by up to a minute. The accepted grammar
                # promises a precision the loop does not deliver.
                time.sleep(60)  # Check every minute
    except FileNotFoundError:
        print(f"Error: Configuration file not found: {args.config}")  # Console output for critical error
        exit(1)
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in configuration file: {args.config}")  # Console output for critical error
        exit(1)
    except ValueError as e:
        print(f"Error: Invalid configuration: {e}")  # Console output for critical error
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}") # Console output for unexpected error
        logging.exception("An unexpected error occurred.") # Log the full traceback.
        exit(1)


if __name__ == "__main__":
    main()