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
    template_data=None,
):

    connection = get_connection()
    template_data = template_data or {}
    
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
            rec_name = recipient.get("name", "").strip() if recipient.get("name") else ""
            rec_email = recipient.get("email", "").strip() if recipient.get("email") else ""

            if not rec_email:
                continue

            # -------------------------------
            # Select HTML Template
            # -------------------------------
            if email_template == "standard" or email_template == "normal":
                template_name = "standard_email.html"

            elif email_template == "ce":
                template_name = "CE_email_template.html"

            elif email_template == "functional":
                template_name = "supply_chain_email.html"

            elif email_template == "poster":
                template_name = "poster.html"

            elif email_template == "CE_supplychainposter":
                template_name = "CE_supplychainposter.html"

            else:
                template_name = "standard_email.html"

            context = {
                "name": rec_name,
                "email": rec_email,
                "description": description,
                "has_image": bool(image_bytes),
            }
            if template_data:
                context.update(template_data)

            html_content = render_to_string(
                template_name,
                context,
            )
            # -------------------------------
            # Plain Text Version
            # -------------------------------
            company_name = template_data.get("company_name") or "InESS Solutions"
            footer_name = template_data.get("footer_text") or company_name
            cta_t = template_data.get("cta_text")
            cta_u = template_data.get("cta_url")
            p_content = template_data.get("poster_content")

            cta_block = f"\n\n{cta_t}: {cta_u}" if (cta_t and cta_u) else ""
            poster_block = f"\n\n{p_content}" if p_content else ""

            if email_template in ["standard", "normal"]:
                greeting = f"Dear {rec_name},\n\n" if rec_name else ""
                text_content = f"{greeting}{description}{poster_block}{cta_block}"
            elif email_template == "poster":
                greeting = f"Hello {rec_name},\n\n" if rec_name else ""
                text_content = f"""{greeting}{description}{poster_block}{cta_block}

Please view this email in HTML mode to see the poster.

Regards,
{footer_name}
"""
            else:
                greeting = f"Hello {rec_name},\n\n" if rec_name else ""
                text_content = f"""{greeting}{description}{poster_block}{cta_block}

Best regards,
{footer_name}
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
                to=[rec_email],
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
                    recipient_name=rec_name,
                    recipient_email=rec_email,
                    subject=subject,
                    email_template=email_template,
                    status="Sent",
                )

            except Exception as e:

                EmailLog.objects.create(
                    sent_by=user,
                    recipient_name=rec_name,
                    recipient_email=rec_email,
                    subject=subject,
                    email_template=email_template,
                    status="Failed",
                    error_message=str(e),
                )

    finally:

        connection.close()