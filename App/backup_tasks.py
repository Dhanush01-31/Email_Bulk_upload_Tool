from email.mime.image import MIMEImage
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.conf import settings
from .models import EmailLog

def send_bulk_email_task(
    subject,
    description,
    recipients,
    user,
    description_image=None,
    attachments=None,
):

    connection = get_connection()

    try:

        connection.open()

        image_bytes = None
        image_name = None

        if description_image:
            image_bytes = description_image.read()
            image_name = description_image.name

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

        for recipient in recipients:

            html_content = render_to_string(
                "supply_chain_email.html",
                {
                    "name": recipient["name"],
                    "email": recipient["email"],
                    "description": description,
                    "has_image": bool(image_bytes),
                },
            )

            text_content = f"""
Hello {recipient['name']} Sir/Mam,

{description}

Regards,
InESS Consulting
"""

            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient["email"]],
                connection=connection,
            )

            email.attach_alternative(
                html_content,
                "text/html",
            )

            if image_bytes:

                image = MIMEImage(image_bytes)

                image.add_header(
                    "Content-ID",
                    "<description_image>"
                )

                image.add_header(
                    "Content-Disposition",
                    "inline",
                    filename=image_name
                )

                email.attach(image)

            for filename, content, mimetype in attachment_data:

                email.attach(
                    filename,
                    content,
                    mimetype,
                )

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
