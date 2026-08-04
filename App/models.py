from django.db import models
from django.contrib.auth.models import User


class EmailLog(models.Model):

    STATUS_CHOICES = [
        ("Sent", "Sent"),
        ("Failed", "Failed"),
    ]

    sent_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_logs",
    )

    recipient_name = models.CharField(
        max_length=150
    )

    recipient_email = models.EmailField()

    subject = models.CharField(
        max_length=255
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="Sent",
    )

    error_message = models.TextField(
        blank=True,
        null=True,
    )

    sent_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:

        db_table = "email_logs"

        ordering = ["-sent_at"]

        verbose_name = "Email Log"

        verbose_name_plural = "Email Logs"

    def __str__(self):

        return f"{self.recipient_email} ({self.status})"