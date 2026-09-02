from django.test import TransactionTestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from .models import EmailLog
from pytest_django.asserts import assertRedirects,assertContains,assertTemplateUsed,assertNotContains
import pytest
from django.urls import reverse
from django.contrib.messages import get_messages
import csv
import io
import pandas as pd
from unittest.mock import patch,MagicMock
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from App.views import send_bulk_email_view
from App.tasks import send_bulk_email_task
from App.models import EmailLog
from django.core import mail
from django.conf import settings
from datetime import date,timedelta

# class EmailLogExportTest(TransactionTestCase):
#     def setUp(self):
#         self.client = Client()
#         self.user = User.objects.create_user(username="testuser", password="password123")
#         self.client.login(username="testuser", password="password123")

#     def test_export_email_logs_timezone(self):
#         # Create a log entry
#         log = EmailLog.objects.create(
#             sent_by=self.user,
#             recipient_name="Test Recipient",
#             recipient_email="test@example.com",
#             subject="Test Subject",
#             status="Sent"
#         )
        
#         # Reload log from DB
#         log.refresh_from_db()
#         sent_at_utc = log.sent_at
#         local_sent_at = timezone.localtime(sent_at_utc)
#         expected_time_str = local_sent_at.strftime("%Y-%m-%d %H:%M:%S")

#         # Request export logs view
#         response = self.client.get("/export-logs/")
#         self.assertEqual(response.status_code, 200)
#         self.assertEqual(response['Content-Type'], 'text/csv')
        
#         # Read CSV content (handling BOM if present)
#         content = response.content.decode('utf-8-sig')
#         csv_reader = csv.reader(io.StringIO(content))
#         rows = list(csv_reader)
        
#         # The CSV has headers:
#         # S.No, Recipient Name, Recipient Email, Subject, Status, Error Message, Sent At
#         self.assertGreater(len(rows), 1)
#         data_row = rows[1]
        
#         self.assertEqual(data_row[1], "Test Recipient")
#         self.assertEqual(data_row[2], "test@example.com")
#         self.assertEqual(data_row[3], "Test Subject")
#         self.assertEqual(data_row[4], "Sent")
#         self.assertEqual(data_row[6], expected_time_str)

#     def test_bulk_email_upload_filtering(self):
#         # Prepare post data with some blank/nan/missing rows
#         csv_data = (
#             "Name,Email\n"
#             "John Doe,john@example.com\n"
#             "NaN,nan@example.com\n"
#             ",emptyemail@example.com\n"
#             "Missing Email,\n"
#             ",\n"
#         )
        
#         response = self.client.post("/send-bulk-email/", {
#             "subject": "Test CSV Upload",
#             "description": "This is a test description",
#             "email_template": "ce",
#             "excel_csv_data": csv_data,
#         })
        
#         # Check that it redirected to dashboard
#         self.assertEqual(response.status_code, 302)
        


#         # Check that only 1 EmailLog record was created (for John Doe)
#         logs = EmailLog.objects.filter(subject="Test CSV Upload")
#         self.assertEqual(logs.count(), 1)
#         self.assertEqual(logs[0].recipient_name, "John Doe")
#         self.assertEqual(logs[0].recipient_email, "john@example.com")
        
#         # Ensure no logs with NaN/nan strings were created in database
#         self.assertFalse(EmailLog.objects.filter(recipient_name__iexact="nan").exists())
#         self.assertFalse(EmailLog.objects.filter(recipient_email__iexact="nan").exists())

# checking pages are working well
# -----------------------------------------------------pages Validation -------------------------------------------------------------------
# Home page testcase
def test_homeview(client):
    response = client.get("/")
    assert response.status_code == 200
    assertTemplateUsed(response,'home.html')

# Login page testcase
def test_loginView(client):
    response = client.get("/login/")
    assert response.status_code == 200
    assertTemplateUsed(response,'login.html')

# Regiter page testcase.
def test_RegisterView(client):
    response = client.get('/register/')
    assert response.status_code == 200
    assertTemplateUsed(response,'register.html')

# Dashboard Page Testcases.
def test_dashboard(client):
    response = client.get('/dashboard/')
    assert response.status_code == 302
    assertRedirects(response,"/login/?next=/dashboard/")

#------------------------------------- Validation for Login and Reegister View ----------------------------------------------------------------
""" Login page Validations """
# Login success
@pytest.mark.django_db
def test_login_success(client):
    User.objects.create_user(username='dhanush',password='dhanush245')
    response =  client.post('/login/',{
        "username":"dhanush",
        "password":"dhanush245"
    })
    assertRedirects(response,'/dashboard/')
    assert response.wsgi_request.user.is_authenticated

# login failed Success
@pytest.mark.django_db
def test_login_fails(client):
    User.objects.create_user(username="dhanush",password='password123')
    response = client.post('/login/',{
        "username" : "dhanush",
        "password" : "wrongpassword"
        })
    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated


# login username empty fields
def test_login_usernamefield_empty(client):
    response = client.post('/login/',{
            "username" : "",
            "password" : "password"
    })
    assert response.status_code == 200
    assertTemplateUsed(response,'login.html')

# login password empty fields
def test_login_passwordfield_empty(client):
    response = client.post('/login/',{
                "username" : "",
                "password" : "password"
        })
    assert response.status_code == 200
    assertTemplateUsed(response,'login.html')


""" Register Page Testcases """
@pytest.mark.django_db
def test_register_sucessfull(client):
    response = client.post('/register/',{
        "username":"dhanush",
        "email" : "sample@gmail.com",
        "password":"dhanush245",
        "confirm_password":"dhanush245"
    })
    assertRedirects(response,'/login/')
    assert User.objects.filter(username__iexact='dhanush').exists()
    assert User.objects.filter(email__iexact='sample@gmail.com').exists()

# user not existed in the database
@pytest.mark.django_db
def test_register_doesnot_exist(client):
    User.objects.create_user(username='dhanush',email='old@example.com',password='dhanush245')
    response = client.post('/register/',{
        "username":'Dhanush',
        "email":"new@example.com",
        "password":"dhanush245",
        "confirm_password":"dhanush245"
    })
    assertRedirects(response,'/register/')
    assert User.objects.filter(username__iexact='dhanush').count() == 1


# Duplicate email is not exists Testcase.
@pytest.mark.django_db
def test_email_doesnot_exists(client):
    User.objects.create_user(username="dhanush",email="dhanush245@gmail.com",password='dhanush245')
    response = client.post('/register/',{
        "username":'dhanush',
        "email":"dhanushsample@gmail.com",
        "password":"password123",
        "confirm_password":"password123"
    })
    assertRedirects(response,'/register/')
    assert User.objects.filter(email__iexact='dhanush245@gmail.com').count() == 1

# password Mismatch
@pytest.mark.django_db
def test_passsword_mismatch(client):
    response = client.post('/register/',{
        "username":'johnathan',
        "email":'john123@gmail.com',
        "password":'originalpassword',
        "Confirm_password": "differentpassword"
    })

    assertRedirects(response,'/register/')
    assert not User.objects.filter(username__iexact='johnathan').exists()

# Empty Register fields Testcase
@pytest.mark.django_db
def test_Registerfileds_empty(client):
    response = client.post('/register/',{
            "username":'',
            "email":'',
            "password":'',
            "Confirm_password": ""
        })
    assertRedirects(response,'/register/')
    assert User.objects.count() == 0


# Logout Testcase.
@pytest.mark.django_db
def test_logout(client):
    user = User.objects.create_user(username='Johnathan',password='password123')
    client.force_login(user)

    assert "_auth_user_id" in client.session

    logout_page = reverse('logout')
    response = client.get(logout_page)

    assertRedirects(response,'/login/',status_code=302)

    assert "_auth_user_id" not in client.session

    messages = list(get_messages(response.wsgi_request))
    assert len(messages) == 1
    assert str(messages[0]) == "Logged out successfully."
    assert messages[0].tags == "success"


# Logout Authenticated Testcase.
def test_logout_authenticate(client):
    logout_page = reverse('logout')
    response = client.get(logout_page)

    assertRedirects(response,'/login/?next=/logout/',status_code=302)

#---------------------------------------------- Bulk Email Upload Validation -----------------------------------------------------------------------

VIEW_MODULE = "App.views"

@pytest.fixture
def auth_user(db):
    return User.objects.create_user(username="testuser",password='password123')

@pytest.fixture
def auth_client(client,auth_user):
    client.force_login(auth_user)
    return client

@pytest.fixture
def sample_csv_file():
    content = b"name,email\nAlice,alice@example.com\nBob,bob@example.com"
    return SimpleUploadedFile('recipients.csv',content,content_type="text/csv")

@pytest.mark.django_db
class TestSendBulkEmail:
    url = reverse("send_bulk_email")
    dashboard_url = reverse('dashboard')

    def get_messages_texts(self,response):
        return [m.message for m in get_messages(response.wsgi_request)]

    def test_unauthenticated_redirects_to_login(self,client):
        response = client.get(self.url)
        expected_url = f'{reverse('login')}?next={self.url}'
        assertRedirects(response,expected_url,status_code=302)

    def test_authenticated_redirects_to_dashboard(self,auth_client):
        response = auth_client.get(self.url)
        assertRedirects(response,self.dashboard_url,status_code=302)

    def test_missing_subject_shows_error(self,auth_client):
        payload = {
            "subject":"",
            "description":"Valid Description",
            'email_template':'ce'
        }
        response = auth_client.post(self.url,data=payload)
        assertRedirects(response,self.dashboard_url,status_code=302)
        assert "Please enter email subject." in self.get_messages_texts(response)

    def test_missing_description_shows_error(self,auth_client):
        payload = {
            "subject":"Valid subject",
            "description":"",
            'email_template':'ce'
        }

        response = auth_client.post(self.url,data=payload)
        assertRedirects(response,self.dashboard_url,status_code=302)
        assert "Please enter email description." in self.get_messages_texts(response)

    def test_missing_email_template_shows_error(self,auth_client):
        payload = {
            "subject":"valid subject",
            "description":"valid description",
            "email_template":''
        }
        response = auth_client.post(self.url,data=payload)
        assertRedirects(response,self.dashboard_url,status_code=302)
        assert "Please select the email template" in self.get_messages_texts(response)

    def test_no_file(self,auth_client):
        payload = {
            "subject":"valid subject",
            "description":"valid description",
            "email_template":'ce'
        }
        response = auth_client.post(self.url,data=payload)
        assertRedirects(response,self.dashboard_url,status_code=302)
        assert 'Please upload Excel file.' in self.get_messages_texts(response)

    def test_corrupt_file_shows_read_error(self,auth_client):
        corrupt_file = SimpleUploadedFile(
            "recipients.xlsx", b"not an excel file", content_type="application/vnd.ms-excel"
        )
        payload = {
            "subject": "Subject",
            "description": "Description",
            "email_excel": corrupt_file,
        }
        response = auth_client.post(self.url,data=payload)
        assertRedirects(response,self.dashboard_url,status_code=302)
        messages = self.get_messages_texts(response)
        assert any('Unable to read file:' in m for m in messages)

    def test_missing_required_columns(self,auth_client):
        csv_file = SimpleUploadedFile('recipients.csv',b"name,phone\nAlice,12345",content_type='text/csv')
        payload = {
                "subject": "Subject",
                "description": "Description",
                "email_excel": csv_file,
            } 
        response = auth_client.post(self.url,data=payload)
        assertRedirects(response,self.dashboard_url,status_code=302)
        assert 'Missing columns: email' in self.get_messages_texts(response)

    def test_no_valid_recipients(self,auth_client):
        csv_file = SimpleUploadedFile('recipients.csv',b"name,email\n , \nNan,nan",content_type="text/csv")
        payload = {
                "subject": "Subject",
                "description": "Description",
                "email_excel": csv_file,
                }
        response = auth_client.post(self.url,data=payload)
        assertRedirects(response,self.dashboard_url,status_code=302)
        assert 'No valid recipients found.' in self.get_messages_texts(response)

    @patch(f"{VIEW_MODULE}.send_bulk_email_task")
    def test_sucessful_csv_data_text_input(self,mock_task,auth_client,auth_user):
        payload = {
            "subject": "Test CSV data",
            "description": "Test description",
            'email_template':'ce',
            'excel_csv_data':'name,email\nCharlie,charlie@example.com'
        }
        response = auth_client.post(self.url,data=payload)
        assertRedirects(response,self.dashboard_url)

        mock_task.assert_called_once_with(
            subject = 'Test CSV data',
            description = 'Test description',
            recipients = [{'name':'Charlie','email':'charlie@example.com'}],
            user = auth_user,
            description_image=None,
            attachments = [],
            email_template='ce'
        )

    @patch(f"{VIEW_MODULE}.send_bulk_email_task")
    def test_sucsessfull_file_upload(self,mock_task,auth_user,auth_client,sample_csv_file):
        payload = {
            'subject':"Test File upload",
            'description':'File Description',
            'email_template':'ce',
            'email_excel':sample_csv_file
        }
        response = auth_client.post(self.url,data=payload)
        assertRedirects(response,self.dashboard_url,status_code=302)
        assert 'Emails sent successfully.' in self.get_messages_texts(response)
        mock_task.assert_called_once()
        call_kwargs = mock_task.call_args.kwargs
        assert len(call_kwargs["recipients"]) == 2
        assert call_kwargs["recipients"][0] == {"name": "Alice", "email": "alice@example.com"}
        assert call_kwargs["user"] == auth_user


#-----------------------------------------------------------------Email SMTP Validation-----------------------------------------------------------------------
@pytest.fixture
def test_user(db):
    return User.objects.create_user(username='admin',password='password123')

@pytest.mark.django_db
def Test_mail_successfull(test_user,settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    settings.SERVER_TYPE = 'DEV'
    settings.DEFAULT_FROM_EMAIL = 'noreply@example'

    recipients = [
        {"name": "Alice", "email": "alice@example.com"},
        {"name": "Bob", "email": "bob@example.com"},
    ]

    image_file = SimpleUploadedFile(
        "poster.png", b"fake_png_data", content_type="image/png"
    )

    attachment_file = SimpleUploadedFile(
        "document.pdf", b"fake_pdf_data", content_type="application/pdf"
    )

    with patch('App.tasks.render_to_string',return_value = "<p>Test HTML"):
        send_bulk_email_task(
            subject="Test Subject",
            description="Test Description",
            recipients=recipients,
            user=test_user,
            description_image=image_file,
            attachments=[attachment_file],
            email_template="ce",
        )

    assert len(mail.outbox) == 2
    first_email = mail.outbox[0]
    assert first_email.to == ["alice@example.com"]
    assert first_email.subject == "Test Subject"
    assert first_email.cc == ["dhanusharumugam@inessconsulting.com"]  # Because SERVER_TYPE="DEV"
    assert "Hello Alice," in first_email.body

    assert len(first_email.alternatives) == 1
    assert first_email.alternatives[0][1] == "text/html"
    assert len(first_email.attachments) == 2  # image + PDF

    logs = EmailLog.objects.filter(sent_by=test_user)
    assert logs.count() == 2
    assert all(log.status == "Sent" for log in logs)
    assert set(logs.values_list("recipient_email", flat=True)) == {
        "alice@example.com",
        "bob@example.com",
    }

@pytest.mark.django_db
def test_send_bulk_email_task_records_failure_on_exception(test_user, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.SERVER_TYPE = "PROD"
    settings.DEFAULT_FROM_EMAIL = "noreply@example.com"

    recipients = [{"name": "Charlie", "email": "charlie@example.com"}]

    with patch("App.tasks.render_to_string", return_value="<p>Error Test</p>"):
        # Force email.send() to raise an exception
        with patch("django.core.mail.EmailMultiAlternatives.send", side_effect=Exception("SMTP Timeout")):
            send_bulk_email_task(
                subject="Failing Email",
                description="This should fail",
                recipients=recipients,
                user=test_user,
            )

    # Assert EmailLog caught the exception and marked status as 'Failed'
    log = EmailLog.objects.get(recipient_email="charlie@example.com")
    assert log.status == "Failed"
    assert "SMTP Timeout" in log.error_message

  
#---------------------------------------------------------------Email logs Validation ----------------------------------------------------------------------
@pytest.fixture
def email_user(db):
    return User.objects.create(username='Testuser',password='password123')


@pytest.fixture
def email_client(client,email_user):
    client.force_login(email_user)
    return client

@pytest.fixture
def sample_logs(db,email_client,email_user):
    today = date.today()
    logs = [
        EmailLog.objects.create(
            sent_by=email_user,
            recipient_name="Alice",
            recipient_email="alice@example.com",
            subject="Invoice 1",
            status="Sent",
            sent_at=today - timedelta(days=5),
        ),
        EmailLog.objects.create(
            sent_by=email_user,
            recipient_name="Bob",
            recipient_email="bob@example.com",
            subject="Invoice 2",
            status="Failed",
            sent_at=today - timedelta(days=2),
        ),
        EmailLog.objects.create(
            sent_by=email_user,
            recipient_name="Charlie",
            recipient_email="charlie@example.com",
            subject="Invoice 3",
            status="Sent",
            sent_at=today,
        ),
    ]
    return logs


@pytest.mark.django_db
class TestEmailLogsView:
    url = reverse('email_logs')

    def test_unauthenicated_redirects_to_login(self,client):
        response = client.get(self.url)
        expected_url = f"{reverse('login')}?next={self.url}"
        assertRedirects(response,'/login/?next=/email-logs/',status_code=302)

    def test_view_renders_sucessfully(self,email_client,sample_logs):
        response = email_client.get(self.url)
        assertTemplateUsed(response,'email_logs.html')
        assert response.status_code == 200
        assert len(response.context["logs"]) == 3
        assert response.context["status"]==""
        assert response.context["start_date"]==""
        assert response.context["end_date"]==""

    def test_filter_by_status_sent(self,email_client,sample_logs):
        response = email_client.get(self.url,{"status":"Sent"})
        assert response.status_code == 200
        logs = response.context['logs']
        assert len(logs)==2
        assert all(log.status == "Sent" for log in logs)
        assert response.context['status']=='Sent'

    def test_filter_by_status_failed(self,email_client,sample_logs):
        response = email_client.get(self.url,{"status":"Failed"})
        assertTemplateUsed(response,'email_logs.html')
        assert response.status_code == 200
        logs = response.context['logs']
        assert len(logs) == 1
        assert all(log.status == 'Failed' for log in logs)
        assert response.context['status'] == 'Failed'

    def test_invalid_status_ignored(self, email_client, sample_logs):
        # Passing an invalid status should skip the filter
        response = email_client.get(self.url, {"status": "Pending"})

        assert response.status_code == 200
        assert len(response.context["logs"]) == 3
        assert response.context["status"] == "Pending"

    def test_filter_by_start_date(self, email_client, sample_logs):
        filter_date = (date.today() - timedelta(days=2)).isoformat()

        response = email_client.get(
            self.url,
            {"start_date": filter_date}
        )

        assert response.status_code == 200

        logs = response.context["logs"]
        

    def test_filter_by_end_date(self, email_client, sample_logs):
        filter_date = (date.today() - timedelta(days=2)).isoformat()

        response = email_client.get(
            self.url,
            {"end_date": filter_date}
        )

        assert response.status_code == 200

        logs = response.context["logs"]

    def test_pagination_splits_records(self, email_client, test_user):
        # Create 15 records to verify pagination of 10 per page
        for i in range(15):
            EmailLog.objects.create(
                sent_by=test_user,
                recipient_name=f"User {i}",
                recipient_email=f"user{i}@example.com",
                subject=f"Bulk {i}",
                status="Sent",
            )

        # First page should contain 10 items
        response_page_1 = email_client.get(self.url)
        assert len(response_page_1.context["logs"]) == 10
        assert response_page_1.context["logs"].has_next() is True

        # Second page should contain the remaining 5 items
        response_page_2 = email_client.get(self.url, {"page": 2})
        assert len(response_page_2.context["logs"]) == 5
        assert response_page_2.context["logs"].has_previous() is True

