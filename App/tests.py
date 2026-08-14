from django.test import TransactionTestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from .models import EmailLog
import csv
import io

class EmailLogExportTest(TransactionTestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username="testuser", password="password123")
        self.client.login(username="testuser", password="password123")

    def test_export_email_logs_timezone(self):
        # Create a log entry
        log = EmailLog.objects.create(
            sent_by=self.user,
            recipient_name="Test Recipient",
            recipient_email="test@example.com",
            subject="Test Subject",
            status="Sent"
        )
        
        # Reload log from DB
        log.refresh_from_db()
        sent_at_utc = log.sent_at
        local_sent_at = timezone.localtime(sent_at_utc)
        expected_time_str = local_sent_at.strftime("%Y-%m-%d %H:%M:%S")

        # Request export logs view
        response = self.client.get("/export-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        
        # Read CSV content (handling BOM if present)
        content = response.content.decode('utf-8-sig')
        csv_reader = csv.reader(io.StringIO(content))
        rows = list(csv_reader)
        
        # The CSV has headers:
        # S.No, Recipient Name, Recipient Email, Subject, Status, Error Message, Sent At
        self.assertGreater(len(rows), 1)
        data_row = rows[1]
        
        self.assertEqual(data_row[1], "Test Recipient")
        self.assertEqual(data_row[2], "test@example.com")
        self.assertEqual(data_row[3], "Test Subject")
        self.assertEqual(data_row[4], "Sent")
        self.assertEqual(data_row[6], expected_time_str)

    def test_bulk_email_upload_filtering(self):
        # Prepare post data with some blank/nan/missing rows
        csv_data = (
            "Name,Email\n"
            "John Doe,john@example.com\n"
            "NaN,nan@example.com\n"
            ",emptyemail@example.com\n"
            "Missing Email,\n"
            ",\n"
        )
        
        response = self.client.post("/send-bulk-email/", {
            "subject": "Test CSV Upload",
            "description": "This is a test description",
            "email_template": "ce",
            "excel_csv_data": csv_data,
        })
        
        # Check that it redirected to dashboard
        self.assertEqual(response.status_code, 302)
        


        # Check that only 1 EmailLog record was created (for John Doe)
        logs = EmailLog.objects.filter(subject="Test CSV Upload")
        self.assertEqual(logs.count(), 1)
        self.assertEqual(logs[0].recipient_name, "John Doe")
        self.assertEqual(logs[0].recipient_email, "john@example.com")
        
        # Ensure no logs with NaN/nan strings were created in database
        self.assertFalse(EmailLog.objects.filter(recipient_name__iexact="nan").exists())
        self.assertFalse(EmailLog.objects.filter(recipient_email__iexact="nan").exists())

