import argparse
import logging
import schedule
import time
import datetime
import smtplib
from email.mime.text import MIMEText
import os
import json
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants (configurable via CLI or config file later)
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


def send_email(subject: str, body: str, recipient: str, smtp_server: str, smtp_port: int, sender_email: str) -> None:
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
            server.sendmail(sender_email, recipient, msg.as_string())
        logging.info(f"Email sent successfully to {recipient}")
    except smtplib.SMTPException as e:
        logging.error(f"Error sending email to {recipient}: {e}")
        raise


def create_review_task(permission: Dict, reviewer: Dict, smtp_server: str, smtp_port: int, sender_email: str) -> None:
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
    body = f"""
    Dear {reviewer['name']},

    A review is required for the following permission:

    Description: {permission['description']}
    Details: {permission['permission_details']}

    Please review this permission and ensure it is still appropriate.  

    [Link to review form - Placeholder]

    Thank you,
    The Permission Review System
    """

    try:
        send_email(subject, body, reviewer["email"], smtp_server, smtp_port, sender_email)
    except Exception as e:
        logging.error(f"Failed to send email for {permission['description']} review to {reviewer['email']}: {e}")


def schedule_reviews(config: Dict) -> None:
    """
    Schedules the permission reviews based on the configuration.

    Args:
        config: The configuration dictionary.
    """
    for permission in config["permissions_to_review"]:
        for reviewer in config["reviewers"]:
            schedule_string = permission["review_schedule"]

            def job():
                create_review_task(permission, reviewer, config["smtp_server"], config["smtp_port"], config["sender_email"])

            try:
                # Use eval() with caution; ensure the review_schedule string is from a trusted source.
                # Consider using a safer alternative like a library specifically designed for parsing schedule strings.
                eval(f"schedule.{schedule_string}.do(job)")
                logging.info(f"Scheduled review for {permission['description']} by {reviewer['name']} with schedule: {schedule_string}")
            except Exception as e:
                logging.error(f"Failed to schedule review for {permission['description']} by {reviewer['name']} with schedule: {schedule_string}: {e}")


def send_test_email(smtp_server: str, smtp_port: int, sender_email: str) -> None:
    """
    Sends a test email to ensure email settings are correct.

    Args:
        smtp_server: The SMTP server hostname.
        smtp_port: The SMTP server port.
        sender_email: The sender's email address.
    """
    test_recipient = sender_email  # Send to sender to verify.  Ideally this would be configurable via CLI args.
    subject = "Test Email from Permission Review Tool"
    body = "This is a test email to verify that the email settings are configured correctly."
    try:
        send_email(subject, body, test_recipient, smtp_server, smtp_port, sender_email)
        print("Test email sent successfully. Check your inbox.")  # Added console output for user feedback
    except Exception as e:
        print(f"Failed to send test email: {e}")  # Added console output for user feedback
        logging.error(f"Failed to send test email: {e}")


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
            send_test_email(config["smtp_server"], config["smtp_port"], config["sender_email"])
        else:
            schedule_reviews(config)

            while True:
                schedule.run_pending()
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