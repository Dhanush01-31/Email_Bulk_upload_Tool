import time
import base64
from email.mime.image import MIMEImage
import smtplib

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from .models import EmailLog

User = get_user_model()

@shared_task(bind=True)
def send_bulk_email_task(
    self,
    subject,
    description,
    recipients,
    user_id,
    description_image_data=None,
    attachments_data=None,
    email_template="ce",
    template_data=None,
):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        print(f"User {user_id} not found. Cannot send emails.")
        return

    connection = get_connection()
    template_data = template_data or {}
    
    # ----------------------------------
    # Decode Poster Image Once
    # ----------------------------------
    image_bytes = None
    image_name = None

    if description_image_data:
        image_name = description_image_data.get("name")
        if description_image_data.get("base64"):
            image_bytes = base64.b64decode(description_image_data["base64"])

    # ----------------------------------
    # Decode Attachments Once
    # ----------------------------------
    attachment_items = []

    if attachments_data:
        for file_data in attachments_data:
            file_name = file_data.get("name")
            file_base64 = file_data.get("base64")
            file_content_type = file_data.get("content_type")
            if file_base64:
                file_bytes = base64.b64decode(file_base64)
                attachment_items.append((file_name, file_bytes, file_content_type))

    try:
        connection.open()
        
        recent_cutoff = timezone.now() - timedelta(hours=24)

        # ----------------------------------
        # Send Email to Each Recipient
        # ----------------------------------
        for recipient in recipients:
            rec_name = recipient.get("name", "").strip() if recipient.get("name") else ""
            rec_email = recipient.get("email", "").strip() if recipient.get("email") else ""

            if not rec_email:
                continue

            # IDEMPOTENCY CHECK: Prevent duplicates if server restarts mid-task
            already_sent = EmailLog.objects.filter(
                recipient_email=rec_email,
                subject=subject,
                status="Sent",
                sent_at__gte=recent_cutoff
            ).exists()

            if already_sent:
                print(f"Skipping {rec_email} - Email already sent successfully in the last 24h.")
                continue

            # -------------------------------
            # Select HTML Template
            # -------------------------------
            if email_template in ["standard", "normal"]:
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

            html_content = render_to_string(template_name, context)

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
                text_content = f"{greeting}{description}{poster_block}{cta_block}\n\nPlease view this email in HTML mode to see the poster.\n\nRegards,\n{footer_name}\n"
            else:
                greeting = f"Hello {rec_name},\n\n" if rec_name else ""
                text_content = f"{greeting}{description}{poster_block}{cta_block}\n\nBest regards,\n{footer_name}\n"

            # -------------------------------
            # Create Email
            # -------------------------------
            if settings.SERVER_TYPE in ["DEV", "DEMO"]:
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
            email.attach_alternative(html_content, "text/html")

            # Inline Poster Image
            if image_bytes:
                image = MIMEImage(image_bytes)
                image.add_header("Content-ID", "<description_image>")
                image.add_header("Content-Disposition", "inline", filename=image_name)
                email.attach(image)

            # Attach Files
            for filename, content, mimetype in attachment_items:
                email.attach(filename, content, mimetype)

            # -------------------------------
            # Send Email (With Gmail Fault Tolerance)
            # -------------------------------
            sent_successfully = False
            try:
                email.send()
                sent_successfully = True
            except smtplib.SMTPServerDisconnected:
                # FAULT TOLERANCE: Gmail dropped the connection. Reconnect and try once more.
                print("SMTP Connection dropped by Gmail! Reconnecting...")
                try:
                    connection.open()
                    email.connection = connection
                    email.send()
                    sent_successfully = True
                except Exception as reconnect_e:
                    print(f"Reconnect failed: {reconnect_e}")
                    EmailLog.objects.create(
                        sent_by=user,
                        recipient_name=rec_name,
                        recipient_email=rec_email,
                        subject=subject,
                        email_template=email_template,
                        status="Failed",
                        error_message=str(reconnect_e),
                    )
            except Exception as e:
                # Specific email failed (e.g. bad address format)
                EmailLog.objects.create(
                    sent_by=user,
                    recipient_name=rec_name,
                    recipient_email=rec_email,
                    subject=subject,
                    email_template=email_template,
                    status="Failed",
                    error_message=str(e),
                )
            
            # Save success log
            if sent_successfully:
                EmailLog.objects.create(
                    sent_by=user,
                    recipient_name=rec_name,
                    recipient_email=rec_email,
                    subject=subject,
                    email_template=email_template,
                    status="Sent",
                )
            
            # RATE LIMITING: Sleep 1 second to bypass Gmail Anti-Spam
            time.sleep(1)

    finally:
        connection.close()