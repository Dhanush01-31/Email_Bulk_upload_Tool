from django.contrib import admin
from .models import EmailLog


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):

    list_display = (
        "recipient_name",
        "recipient_email",
        "subject",
        "status",
        "sent_by",
        "sent_at",
    )

    search_fields = (
        "recipient_name",
        "recipient_email",
        "subject",
    )

    list_filter = (
        "status",
        "sent_at",
        "sent_by",
    )

    ordering = (
        "-sent_at",
    )

    readonly_fields = (
        "recipient_name",
        "recipient_email",
        "subject",
        "status",
        "error_message",
        "sent_by",
        "sent_at",
    )

    list_per_page = 20