# src/mlb_today/blueprints/bp_email.py

import logging
import json
import os
from datetime import datetime

import azure.functions as func
from jinja2 import Environment, FileSystemLoader, select_autoescape

import src.mlb_today.config as config
# You will need an EmailService to handle the sending logic
from src.mlb_today.services.email_service import EmailService

bp = func.Blueprint()

# --- Configuration ---
EMAIL_RECIPIENTS = config.PROBABLES_TO_EMAIL_STR

# --- Jinja2 Environment Setup ---
# This assumes a 'templates' directory exists alongside your 'blueprints' and 'services' directories
# e.g., src/mlb_today/templates/
template_path = os.path.join(os.path.dirname(__file__), '..', 'templates')
jinja_env = Environment(
    loader=FileSystemLoader(template_path),
    autoescape=select_autoescape(['html', 'xml'])
)


@bp.blob_trigger(
    arg_name="emailblob",
    path="email-data/email_data.json",  # Matches the container/blob name from bp_probables
    connection="STORAGE_CONNECTION_STRING"  # Name of the app setting for the connection string
)
def create_and_send_email(emailblob: func.InputStream) -> None:
    """
    Triggers when email_data.json is created, generates an HTML email body
    from a Jinja2 template, and sends the email.
    """
    logging.info(f"Blob trigger processed blob: {emailblob.name}")

    try:
        # 1. Read and parse the blob data
        blob_data_str = emailblob.read().decode('utf-8')
        email_data = json.loads(blob_data_str)

        # 2. Load the Jinja2 template
        template = jinja_env.get_template("email.jinja2")

        # 3. Render the template with the data
        html_body = template.render(
            probables=email_data.get("probables"),
            batting=email_data.get("batting")
        )

        # 4. Send the email
        email_service = EmailService()
        to_recipients = email_service.create_email_recipients(EMAIL_RECIPIENTS)

        if not to_recipients:
            logging.warning("No email recipients configured. Skipping email send.")
            return

        subject = f"MLB Today: Probable Pitchers & Top Hitters for {datetime.now().strftime('%B %d, %Y')}"
        email_service.send_email_with_acs(
            subject=subject,
            html_body=html_body,
            to_recipients=to_recipients
        )

        logging.info("Successfully generated and sent email.")

    except json.JSONDecodeError:
        logging.error(f"Failed to parse JSON from blob: {emailblob.name}", exc_info=True)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
