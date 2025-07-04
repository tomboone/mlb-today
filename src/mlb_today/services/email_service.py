"""Service for sending emails using Azure Communication Services."""
import logging

from azure.communication.email import EmailClient

import src.mlb_today.config as config

ACS_CONNECTION_STRING = config.ACS_CONNECTION_STRING
ACS_SENDER_ADDRESS = config.ACS_SENDER_ADDRESS


# noinspection PyMethodMayBeStatic,PyProtectedMember
class EmailService:
    """Service for sending emails using Azure Communication Services."""
    def create_email_recipients(self, email_str_list):
        """
        Converts a comma-separated string of emails to a list of EmailAddress objects.

        Args:
            email_str_list: A comma-separated string of email addresses.
        """
        if not email_str_list:
            return []
        return [{'address': addr.strip()} for addr in email_str_list.split(',') if addr.strip()]

    def send_email_with_acs(self, subject, html_body, to_recipients, cc_recipients=None):
        """Sends an HTML email using Azure Communication Services."""
        if not ACS_CONNECTION_STRING:
            logging.error("ACS_CONNECTION_STRING is not set. Cannot send email.")
            return
        if not ACS_SENDER_ADDRESS:
            logging.error("ACS_SENDER_ADDRESS is not set. Cannot send email.")
            return
        if not to_recipients:
            logging.error("No TO_EMAIL recipients specified. Cannot send email.")
            return

        try:
            email_client = EmailClient.from_connection_string(ACS_CONNECTION_STRING)
            content = {
                "subject": subject,
                "html": html_body
            }

            if isinstance(to_recipients, str):
                to_list = self.create_email_recipients(to_recipients)
            elif isinstance(to_recipients, list):
                to_list = to_recipients
            else:
                to_list = [addr.strip() for addr in to_recipients]

            recipients_obj = to_list

            if cc_recipients:
                if isinstance(cc_recipients, str):
                    cc_list = self.create_email_recipients(cc_recipients)
                elif isinstance(cc_recipients, list):
                    cc_list = cc_recipients
                else:
                    cc_list = [addr.strip() for addr in cc_recipients]
            else:
                cc_list = None

            message = {
                "content": content,
                "recipients": {
                    "to": recipients_obj,
                    "cc": cc_list if cc_list else ""
                },
                "senderAddress": ACS_SENDER_ADDRESS
            }

            poller = email_client.begin_send(message)
            result = poller.result()

            if poller.done() and result:
                logging.info(f"Email sent successfully via ACS.")
            else:
                logging.error(
                    f"ACS Email send operation finished, but status indicates failure or is unknown. Poller status: "
                    f"{poller.status()}"
                )
                if hasattr(poller, '_operation') and hasattr(poller._operation, 'details'):
                    logging.error(f"ACS Error details: {poller._operation.details}")

        except Exception as e:
            logging.error(f"Failed to send email via ACS: {e}", exc_info=True)
