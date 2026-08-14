# Pandas
import pandas as pd

# Django
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout,get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone


# --- Email Validation and Paginator
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator


# Models and tasks
from .models import EmailLog
from .tasks import send_bulk_email_task

# Os 
import os
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse


User = get_user_model()

# -------------------------
# Home
# -------------------------

def home(request):

    return render(request, "home.html")


# -------------------------
# Register
# -------------------------

def register_view(request):

    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":

        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password")
        confirm = request.POST.get("confirm_password")

        if not username or not email or not password:

            messages.error(request, "All fields are required.")
            return redirect("register")

        if password != confirm:

            messages.error(request, "Passwords do not match.")
            return redirect("register")

        if User.objects.filter(username__iexact=username).exists():

            messages.error(request, "Username already exists.")
            return redirect("register")

        if User.objects.filter(email__iexact=email).exists():

            messages.error(request, "Email already exists.")
            return redirect("register")

        User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        messages.success(request, "Registration Successful.")

        return redirect("login")

    return render(request, "register.html")


# -------------------------
# Login
# -------------------------

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    # Get next URL
    next_url = request.GET.get("next") or request.POST.get("next")

    # Normalize invalid values
    if next_url in ("", "None", None):
        next_url = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        # Empty field validation
        if not username:
            messages.error(request, "Username is required.")
            return render(request, "login.html", {"next": next_url})

        if not password:
            messages.error(request, "Password is required.")
            return render(request, "login.html", {"next": next_url})

        # Check username exists
        if not User.objects.filter(username=username).exists():
            messages.error(request, "Username does not exist.")
            return render(request, "login.html", {"next": next_url})

        # Authenticate
        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is None:
            messages.error(request, "Incorrect password.")
            return render(request, "login.html", {"next": next_url})

        # Login
        login(request, user)

        # Redirect to next page if valid
        if next_url and url_has_allowed_host_and_scheme(
            url=next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)

        # Default redirect
        return redirect("dashboard")

    return render(request, "login.html", {"next": next_url})


# -------------------------
# Logout
# -------------------------

@login_required(login_url="login")
def logout_view(request):

    logout(request)

    messages.success(request, "Logged out successfully.")

    return redirect("login")


# -------------------------
# Dashboard
# -------------------------

@login_required(login_url="login")
def dashboard(request):
    logs_queryset = EmailLog.objects.filter(sent_by=request.user).order_by("-sent_at")

    # Filters
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    status = request.GET.get("status")

    if start_date:
        logs_queryset = logs_queryset.filter(sent_at__date__gte=start_date)
    if end_date:
        logs_queryset = logs_queryset.filter(sent_at__date__lte=end_date)
    if status in ["Sent", "Failed"]:
        logs_queryset = logs_queryset.filter(status=status)

    # Slice only if no filters are applied, or show up to 50 if filtered
    if not (start_date or end_date or status):
        logs = logs_queryset[:10]
    else:
        logs = logs_queryset[:50]

    context = {
        "total_sent": EmailLog.objects.filter(
            sent_by=request.user,
            status="Sent"
        ).count(),

        "total_failed": EmailLog.objects.filter(
            sent_by=request.user,
            status="Failed"
        ).count(),

        "total_logs": EmailLog.objects.filter(
            sent_by=request.user
        ).count(),

        "logs": logs,
        "start_date": start_date or "",
        "end_date": end_date or "",
        "status": status or "",
    }

    return render(
        request,
        "dashboard.html",
        context
    )


# -------------------------
# Upload Excel
# -------------------------

@login_required(login_url="login")
def send_bulk_email_view(request):

    if request.method != "POST":
        return redirect("dashboard")

    subject = request.POST.get("subject", "").strip()
    description = request.POST.get("description", "").strip()

    email_excel = request.FILES.get("email_excel")
    description_image = request.FILES.get("description_image")
    attachments = request.FILES.getlist("attachments")
    email_template = request.POST.get("email_template", "ce")

    if not email_template:
        messages.error(request,"Please select the email template")
        return redirect('dashboard')
    
    if not subject:
        messages.error(request, "Please enter email subject.")
        return redirect("dashboard")

    if not description:
        messages.error(request, "Please enter email description.")
        return redirect("dashboard")

    excel_csv_data = request.POST.get("excel_csv_data", "").strip()

    try:
        if excel_csv_data:
            import io
            df = pd.read_csv(io.StringIO(excel_csv_data))
        else:
            if not email_excel:
                messages.error(request, "Please upload Excel file.")
                return redirect("dashboard")

            if email_excel.name.endswith('.csv'):
                df = pd.read_csv(email_excel)
            else:
                df = pd.read_excel(email_excel)

    except Exception as e:
        import traceback
        traceback.print_exc()
        messages.error(request, f"Unable to read file: {str(e)}")
        return redirect("dashboard")

    df.columns = df.columns.str.strip().str.lower()

    required_columns = [
        "name",
        "email",
    ]

    missing = [c for c in required_columns if c not in df.columns]

    if missing:

        messages.error(
            request,
            f"Missing columns: {', '.join(missing)}"
        )

        return redirect("dashboard")

    # Replace any NaN/None values from pandas with empty strings
    df = df.fillna("")

    recipients = []

    for _, row in df.iterrows():

        name = str(row["name"]).strip()
        email = str(row["email"]).strip()

        if name and email and name.lower() != "nan" and email.lower() != "nan":

            recipients.append({
                "name": name,
                "email": email,
            })

    if not recipients:

        messages.error(request, "No valid recipients found.")
        return redirect("dashboard")

    send_bulk_email_task(
        subject=subject,
        description=description,
        recipients=recipients,
        user=request.user,
        description_image=description_image,
        attachments=attachments,
        email_template=email_template,
    )

    messages.success(request, "Emails sent successfully.")

    return redirect("dashboard")


# ----   Email logs page view
@login_required(login_url="login")
def email_logs(request):
    logs_list = EmailLog.objects.all().order_by("-sent_at")

    # Filters
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    status = request.GET.get("status")

    if start_date:
        logs_list = logs_list.filter(sent_at__date__gte=start_date)
    if end_date:
        logs_list = logs_list.filter(sent_at__date__lte=end_date)
    if status in ["Sent", "Failed"]:
        logs_list = logs_list.filter(status=status)

    # Show 10 records per page
    paginator = Paginator(logs_list, 10)

    # Get current page number
    page_number = request.GET.get("page")

    # Get page object
    logs = paginator.get_page(page_number)

    return render(request, "email_logs.html", {
        "logs": logs,
        "start_date": start_date or "",
        "end_date": end_date or "",
        "status": status or "",
    })


# ----   Export email logs to Excel/CSV view
@login_required(login_url="login")
def export_email_logs(request):
    import csv
    logs = EmailLog.objects.all().order_by("-sent_at")

    # Filters
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")
    status = request.GET.get("status")
    export_all = request.GET.get("export_all") == "true"

    if not export_all:
        if start_date:
            logs = logs.filter(sent_at__date__gte=start_date)
        if end_date:
            logs = logs.filter(sent_at__date__lte=end_date)
        if status in ["Sent", "Failed"]:
            logs = logs.filter(status=status)

    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="email_logs.csv"'},
    )
    
    # Write UTF-8 BOM so Excel opens it with correct unicode encoding
    response.write(b'\xef\xbb\xbf')

    writer = csv.writer(response)
    writer.writerow([
        "S.No",
        "Recipient Name",
        "Recipient Email",
        "Subject",
        "Status",
        "Error Message",
        "Sent At",
    ])

    for i, log in enumerate(logs, 1):
        local_sent_at = timezone.localtime(log.sent_at) if log.sent_at else None
        sent_at_str = local_sent_at.strftime("%Y-%m-%d %H:%M:%S") if local_sent_at else ""
        writer.writerow([
            i,
            log.recipient_name,
            log.recipient_email,
            log.subject,
            log.status,
            log.error_message or "",
            sent_at_str,
        ])

    return response
    
#-----------downlaod Template
    
def download_template(request):
    file_path = os.path.join(
        settings.BASE_DIR,
        "resources",
        "mail_details.xlsx"
    )
    
    print(file_path)
    print(os.path.isfile(file_path))

    if os.path.isfile(file_path):
        return FileResponse(
            open(file_path, "rb"),
            as_attachment=True,
            filename="mail_details.xlsx"
        )

    raise Http404("Template file not found.")



# ----------- preview email template
from django.template.loader import render_to_string

@login_required(login_url="login")
def email_preview(request):
    if request.method == "POST":
        template_name = request.POST.get("email_template", "ce")
        name = request.POST.get("name", "Recipient Name")
        email = request.POST.get("email", "recipient@example.com")
        description = request.POST.get("description", "")
        has_image = request.POST.get("has_image") == "true"
        
        if template_name == "ce":
            template_path = "CE_email_template.html"
        elif template_name == "functional":
            template_path = "supply_chain_email.html"
        elif template_name == "poster":
            template_path = "poster.html"
        elif template_name == "CE_supplychainposter":
            template_path = "CE_supplychainposter.html"
        else:
            template_path = "CE_email_template.html"
            
        html_content = render_to_string(
            template_path,
            {
                "name": name,
                "email": email,
                "description": description,
                "has_image": has_image,
            },
        )
        
        return HttpResponse(html_content)
    return HttpResponse("POST request required", status=400)



# 404 and 500 Custom handlers.
def custom_404(request, exception):
    return render(request, "404.html", status=404)


def custom_500(request):
    return render(request, "500.html", status=500)


def supply_chain(request):
    return render(request,'supply_chain_email.html')

