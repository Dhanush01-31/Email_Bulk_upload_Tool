from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string

from .models import EmailLog


def send_bulk_email_task(
    subject,
    description,
    recipients,
    user,
    description_image=None,
    attachments=None,
    email_template="ce",
    task=None,
):

    connection = get_connection()

    try:

        # ----------------------------------
        # Open SMTP Connection
        # ----------------------------------
        connection.open()

        # ----------------------------------
        # Read Poster Image Once
        # ----------------------------------
        image_bytes = None
        image_name = None

        if description_image:

            if isinstance(description_image, dict):
                image_bytes = description_image.get("bytes")
                image_name = description_image.get("name")
            else:
                image_bytes = description_image.read()
                image_name = description_image.name

        # ----------------------------------
        # Read Attachments Once
        # ----------------------------------
        attachment_data = []

        if attachments:

            for file in attachments:

                if isinstance(file, dict):
                    attachment_data.append(
                        (
                            file.get("name"),
                            file.get("bytes"),
                            file.get("content_type"),
                        )
                    )
                else:
                    attachment_data.append(
                        (
                            file.name,
                            file.read(),
                            file.content_type,
                        )
                    )

        # ----------------------------------
        # Select Email Template
        # ----------------------------------
        if email_template == "ce":

            template_name = "CE_email_template.html"

        elif email_template == "functional":

            template_name = "supply_chain_email.html"

        elif email_template == "poster":

            template_name = "poster.html"

        else:

            template_name = "CE_email_template.html"

        # ----------------------------------
        # CC Emails
        # ----------------------------------
        CC_EMAILS = [
            "dhanusharumugam@inessconsulting.com"
        ]

        # ----------------------------------
        # Send Email to Each Recipient
        # ----------------------------------
        for recipient in recipients:

            # ----------------------------------
            # Render HTML Content
            # ----------------------------------
            html_content = render_to_string(
                template_name,
                {
                    "name": recipient["name"],
                    "email": recipient["email"],
                    "description": description,
                    "has_image": bool(image_bytes),
                },
            )

            # ----------------------------------
            # Plain Text Content
            # ----------------------------------
            if email_template == "poster":

                text_content = f"""
Hello {recipient['name']},

{description}

Please view this email in HTML mode to see the poster.

Regards,
InESS Consulting
"""

            else:

                text_content = f"""
Hello {recipient['name']},

{description}

Regards,
InESS Consulting
"""

            # ----------------------------------
            # Create Email
            # ----------------------------------
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient["email"]],
                cc=CC_EMAILS,
                connection=connection,
            )

            # ----------------------------------
            # Add HTML Version
            # ----------------------------------
            email.attach_alternative(
                html_content,
                "text/html",
            )

            # ----------------------------------
            # Inline Poster Image
            # ----------------------------------
            if image_bytes:

                image = MIMEImage(image_bytes)

                image.add_header(
                    "Content-ID",
                    "<description_image>",
                )

                image.add_header(
                    "Content-Disposition",
                    "inline",
                    filename=image_name,
                )

                email.attach(image)

            # ----------------------------------
            # Attach Files
            # ----------------------------------
            for filename, content, mimetype in attachment_data:

                email.attach(
                    filename,
                    content,
                    mimetype,
                )

            # ----------------------------------
            # Send Email with Retry
            # ----------------------------------
            max_retries = 2

            email_sent = False
            last_error = None

            for attempt in range(max_retries + 1):

                try:

                    # ------------------------------
                    # Make Sure Connection Is Open
                    # ------------------------------
                    if not connection:

                        connection = get_connection()
                        connection.open()

                    # ------------------------------
                    # Send Email
                    # ------------------------------
                    email.connection = connection

                    email.send()

                    email_sent = True

                    break

                except Exception as e:

                    last_error = e

                    print(
                        f"Email sending failed for "
                        f"{recipient['email']} "
                        f"(Attempt {attempt + 1}/{max_retries + 1}): "
                        f"{str(e)}"
                    )

                    # ------------------------------
                    # Close Broken Connection
                    # ------------------------------
                    try:

                        connection.close()

                    except Exception:

                        pass

                    # ------------------------------
                    # Reconnect for Next Attempt
                    # ------------------------------
                    if attempt < max_retries:

                        try:

                            connection = get_connection()
                            connection.open()

                            print(
                                f"SMTP connection re-established. "
                                f"Retrying {recipient['email']}..."
                            )

                        except Exception as reconnect_error:

                            last_error = reconnect_error

                            print(
                                "Failed to reconnect SMTP: "
                                f"{str(reconnect_error)}"
                            )

            # ----------------------------------
            # Email Log
            # ----------------------------------
            if email_sent:

                EmailLog.objects.create(
                    sent_by=user,
                    recipient_name=recipient["name"],
                    recipient_email=recipient["email"],
                    subject=subject,
                    status="Sent",
                )

                print(
                    f"Email successfully sent to "
                    f"{recipient['email']}"
                )

            else:

                EmailLog.objects.create(
                    sent_by=user,
                    recipient_name=recipient["name"],
                    recipient_email=recipient["email"],
                    subject=subject,
                    status="Failed",
                    error_message=str(last_error),
                )

                print(
                    f"Email permanently failed for "
                    f"{recipient['email']}: "
                    f"{str(last_error)}"
                )

            # ----------------------------------
            # Continue to Next Recipient
            # ----------------------------------
            if task:
                from .models import BulkSendTask
                from django.db.models import F
                BulkSendTask.objects.filter(id=task.id).update(sent_count=F("sent_count") + 1)

        if task:
            from .models import BulkSendTask
            BulkSendTask.objects.filter(id=task.id).update(status="Completed")

    except Exception as e:
        if task:
            from .models import BulkSendTask
            BulkSendTask.objects.filter(id=task.id).update(status="Failed", error_message=str(e))
        raise e

    finally:

        # ----------------------------------
        # Close SMTP Connection
        # ----------------------------------
        try:

            connection.close()

        except Exception:

            pass