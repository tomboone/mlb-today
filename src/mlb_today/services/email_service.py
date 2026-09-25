"""Service for sending emails via SMTP."""
import smtplib
import ssl
from email.message import EmailMessage

import src.mlb_today.config as config
from src.mlb_today.logger import logger

SMTP_HOST = config.SMTP_HOST
SMTP_PORT = config.SMTP_PORT
SMTP_USERNAME = config.SMTP_USERNAME
SMTP_PASSWORD = config.SMTP_PASSWORD
SMTP_SENDER_ADDRESS = config.SMTP_SENDER_ADDRESS


# noinspection PyMethodMayBeStatic
class EmailService:
    """Service for sending emails via SMTP."""
    def create_email_recipients(self, email_str_list: str | None) -> list[str]:
        """
        Converts a comma-separated string of emails to a list of addresses.

        Args:
            email_str_list: A comma-separated string of email addresses.
        """
        if not email_str_list:
            return []
        return [addr.strip() for addr in email_str_list.split(',') if addr.strip()]

    def send_email(
        self,
        subject: str,
        html_body: str,
        to_recipients: str | list[str],
        cc_recipients: str | list[str] | None = None
    ) -> None:
        """Sends an HTML email over SMTP with implicit TLS."""
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            logger.error("SMTP_USERNAME and SMTP_PASSWORD must be set. Cannot send email.")
            return
        if not SMTP_SENDER_ADDRESS:
            logger.error("SMTP_SENDER_ADDRESS is not set. Cannot send email.")
            return

        if isinstance(to_recipients, str):
            to_recipients = self.create_email_recipients(to_recipients)
        if isinstance(cc_recipients, str):
            cc_recipients = self.create_email_recipients(cc_recipients)

        if not to_recipients:
            logger.error("No TO_EMAIL recipients specified. Cannot send email.")
            return

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = SMTP_SENDER_ADDRESS
        message["To"] = ", ".join(to_recipients)
        if cc_recipients:
            message["Cc"] = ", ".join(cc_recipients)
        message.set_content("This email requires an HTML-capable email client.")
        message.add_alternative(html_body, subtype="html")

        try:
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ssl.create_default_context()) as smtp:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
                smtp.send_message(message)
            logger.info(f"Email sent successfully via SMTP ({SMTP_HOST}).")
        except (smtplib.SMTPException, OSError) as e:
            logger.error(f"Failed to send email via SMTP: {e}", exc_info=True)
