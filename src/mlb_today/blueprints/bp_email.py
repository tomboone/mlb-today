""" Azure Function to send email """
import logging
import json
import os
from datetime import datetime

import azure.functions as func
from jinja2 import Environment, FileSystemLoader, select_autoescape, Template

import src.mlb_today.config as config
from src.mlb_today.services.email_service import EmailService

bp = func.Blueprint()

EMAIL_RECIPIENTS: str = config.PROBABLES_TO_EMAIL_STR
EMAIL_BLOB_CONTAINER_NAME: str = config.EMAIL_BLOB_CONTAINER_NAME


def format_time_ampm(iso_string: str) -> str:
    """Jinja2 filter to convert an ISO datetime string to a 12-hour AM/PM format."""
    if not iso_string:
        return ""
    try:
        dt_object = datetime.fromisoformat(iso_string)
        # Format to 12-hour with AM/PM
        formatted_time = dt_object.strftime("%I:%M %p")
        # Remove leading zero for hours like '02:40 PM' -> '2:40 PM'
        if formatted_time.startswith('0'):
            return formatted_time[1:]
        return formatted_time
    except (ValueError, TypeError):
        return iso_string  # Return original string on error


template_path: str = os.path.join(os.path.dirname(__file__), '..', 'templates')
jinja_env: Environment = Environment(
    loader=FileSystemLoader(template_path),
    autoescape=select_autoescape(['html', 'xml'])
)

jinja_env.filters['to_ampm'] = format_time_ampm


@bp.blob_trigger(
    arg_name="emailblob",
    # Correctly format the path with the container name and a blob name pattern.
    # This makes the trigger robust and configurable.
    path=f"{EMAIL_BLOB_CONTAINER_NAME}/{{name}}",
    connection="STORAGE_CONNECTION_STRING"
)
def create_and_send_email(emailblob: func.InputStream) -> None:
    """
    Triggers when a blob is created/updated, generates an HTML email body
    from a Jinja2 template, and sends the email.
    """
    logging.info(f"Blob trigger processed blob: {emailblob.name}")

    try:
        blob_data_str: str = emailblob.read().decode()  # Convert blob bytes to string
        email_data: dict[str, list[dict[str, str]]] = json.loads(blob_data_str)  # Convert JSON to dict

        template: Template = jinja_env.get_template("email.jinja2")  # Load the Jinja2 template

        html_body = template.render(  # Render the template with the data
            probables=email_data.get("probables"),
            batting=email_data.get("batting"),
            pitching=email_data.get("pitching")
        )

        email_service = EmailService()  # Create an instance of EmailService
        to_recipients = email_service.create_email_recipients(EMAIL_RECIPIENTS)  # Create recipients

        if not to_recipients:  # If no email recipients, log and return
            logging.warning("No email recipients configured. Skipping email send.")
            return

        subject = f"MLB Today for {datetime.now().strftime('%B %d, %Y')}"  # Create subject

        email_service.send_email_with_acs(  # Send the email
            subject=subject,
            html_body=html_body,
            to_recipients=to_recipients
        )

        logging.info("Successfully generated and sent email.")

    except json.JSONDecodeError:  # Handle JSON decoding errors
        logging.error(f"Failed to parse JSON from blob: {emailblob.name}", exc_info=True)
    except Exception as e:  # Handle other exceptions
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
