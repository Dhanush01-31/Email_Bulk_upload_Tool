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
):

    connection = get_connection()
    
    # dev branch

    try:

        connection.open()

        # ----------------------------------
        # Read Poster Image Once
        # ----------------------------------
        image_bytes = None
        image_name = None

        if description_image:
            image_bytes = description_image.read()
            image_name = description_image.name

        # ----------------------------------
        # Read Attachments Once
        # ----------------------------------
        attachment_data = []

        if attachments:
            for file in attachments:

                attachment_data.append(
                    (
                        file.name,
                        file.read(),
                        file.content_type,
                    )
                )

        # ----------------------------------
        # Send Email to Each Recipient
        # ----------------------------------
        for recipient in recipients:

            # -------------------------------
            # Select HTML Template
            # -------------------------------
            if email_template == "ce":

                template_name = "CE_email_template.html"

            elif email_template == "functional":

                template_name = "supply_chain_email.html"

            elif email_template == "poster":

                template_name = "poster.html"

            elif email_template == "CE_supplychainposter":

                template_name = "CE_supplychainposter.html"

            else:

                template_name = "CE_email_template.html"

            html_content = render_to_string(
                template_name,
                {
                    "name": recipient["name"],
                    "email": recipient["email"],
                    "description": description,
                    "has_image": bool(image_bytes),
                },
            )

            

            # -------------------------------
            # Plain Text Version
            # -------------------------------
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

            # -------------------------------
            # Create Email
            # -------------------------------
            if settings.SERVER_TYPE == "DEV" or settings.SERVER_TYPE == 'DEMO':
                CC_EMAILS = ["dhanusharumugam@inessconsulting.com"]
            else:
                CC_EMAILS = ["srinithin@inessconsulting.com"]

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient["email"]],
                cc=CC_EMAILS,
                connection=connection,
            )

            email.attach_alternative(
                html_content,
                "text/html",
            )

            # -------------------------------
            # Inline Poster Image
            # -------------------------------
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

            # -------------------------------
            # Attach Files
            # -------------------------------
            for filename, content, mimetype in attachment_data:

                email.attach(
                    filename,
                    content,
                    mimetype,
                )

            # -------------------------------
            # Send Email
            # -------------------------------
            try:

                email.send()

                EmailLog.objects.create(
                    sent_by=user,
                    recipient_name=recipient["name"],
                    recipient_email=recipient["email"],
                    subject=subject,
                    status="Sent",
                )

            except Exception as e:

                EmailLog.objects.create(
                    sent_by=user,
                    recipient_name=recipient["name"],
                    recipient_email=recipient["email"],
                    subject=subject,
                    status="Failed",
                    error_message=str(e),
                )

    finally:

        connection.close()