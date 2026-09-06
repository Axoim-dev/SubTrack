from django.shortcuts import render, redirect, get_object_or_404
from .models import User, Subscription, GoogleAccount
from django.contrib.auth import authenticate, login, logout
from decimal import Decimal
from django.contrib.admin.models import LogEntry
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth
from django.conf import settings
from django.shortcuts import redirect
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from django.contrib.auth import update_session_auth_hash
import time

# Create your views here.

def home(request):
    return render(request, "subscriptions/home.html")



@login_required
def dashboard(request):

    user = request.user

    subscriptions = Subscription.objects.filter(
        user=user
    ).order_by("date_due")

    google_acc = GoogleAccount.objects.filter(user=user).first()

    monthly_spending = sum(
        subscription.amount
        for subscription in subscriptions
    )

    yearly_spending = monthly_spending * Decimal("12")

    active_subscriptions = subscriptions.count()

    return render(
        request,
        "subscriptions/dashboard.html",
        {
            "subscriptions": subscriptions,
            "monthly_spending": monthly_spending,
            "yearly_spending": yearly_spending,
            "active_subscriptions": active_subscriptions,
        }
    )

def signup(request):
    if request.method == "POST":
        email = request.POST["email"]
        name = request.POST["name"]
        username = request.POST["username"]
        password = request.POST["password"]

        if User.objects.filter(username=username).exists():
            return render(
                request,
                "subscriptions/signup.html",
                {"error":"Username already exists"}
            )
        if User.objects.filter(email=email).exists():
            return render(
                request,
                "subscriptions/signup.html",
                {"error":"Email already exists"}
            )
        user = User.objects.create_user(
            email=email,
            password=password,
            username=username
        )
        user.name = name
        user.save()

        login(request, user)
        request.session["gmail_verified"] = False
        return redirect("dashboard")
    return render(request, "subscriptions/signup.html", )


def login_view(request):
    if request.method == "POST":
        username = request.POST["username"]
        password = request.POST["password"]

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            gmail_connected = GoogleAccount.objects.filter(
                user=user
            ).exists()

            request.session["gmail_verified"] = gmail_connected
            return redirect("dashboard")
        return render(request, "subscriptions/login.html", {
            "error":"Invalid username or password"
        })
    return render(request, "subscriptions/login.html")

def logout_view(request):
    logout(request)
    return redirect("home")

@login_required(login_url="login")
def analytics(request):

    user = request.user

    subscriptions = Subscription.objects.filter(user=request.user)

    total_monthly = Decimal("0")
    total_yearly = Decimal("0")

    subscription_costs = []
    category_spending = {}

    for sub in subscriptions:

        if sub.billing_period == "weekly":
            monthly_cost = sub.amount * Decimal("52") / Decimal("12")
            yearly_cost = sub.amount * Decimal("52")

        elif sub.billing_period == "monthly":
            monthly_cost = sub.amount
            yearly_cost = sub.amount * Decimal("12")

        elif sub.billing_period == "yearly":
            monthly_cost = sub.amount / Decimal("12")
            yearly_cost = sub.amount

        else:
            monthly_cost = Decimal("0")
            yearly_cost = Decimal("0")

        total_monthly += monthly_cost
        total_yearly += yearly_cost

        # -------------------------
        # SUBSCRIPTION COSTS
        # -------------------------

        subscription_costs.append({
            "merchant": sub.merchant,
            "amount": round(float(monthly_cost), 2),
        })

        # -------------------------
        # CATEGORY SPENDING
        # -------------------------

        category = sub.get_category_display()

        if category not in category_spending:
            category_spending[category] = Decimal("0")

        category_spending[category] += monthly_cost

    # Most expensive subscriptions first
    subscription_costs.sort(
        key=lambda x: x["amount"],
        reverse=True
    )

    # -------------------------
    # MONTHLY SPENDING
    # -------------------------

    monthly_spending = []

    for month in range(1, 13):

        month_total = Decimal("0")

        for sub in subscriptions:

            if sub.billing_period == "monthly":
                month_total += sub.amount

            elif sub.billing_period == "weekly":
                month_total += (
                    sub.amount * Decimal("52") / Decimal("12")
                )

            elif sub.billing_period == "yearly":
                month_total += sub.amount / Decimal("12")

        monthly_spending.append({
            "month": month,
            "amount": round(float(month_total), 2),
        })

    # -------------------------
    # CATEGORY DATA
    # -------------------------

    category_data = []

    for category, amount in category_spending.items():

        category_data.append({
            "category": category,
            "amount": round(float(amount), 2),
        })

    # -------------------------
    # FINAL ANALYTICS OBJECT
    # -------------------------

    analytics_data = {
        "total_monthly": round(float(total_monthly), 2),
        "total_yearly": round(float(total_yearly), 2),
        "subscription_count": subscriptions.count(),

        "monthly_spending": monthly_spending,

        "subscription_costs": subscription_costs,

        "category_spending": category_data,
    }

    return render(
        request,
        "subscriptions/analytics.html",
        {
            "analytics": analytics_data
        }
    )



@login_required(login_url="login")
def add_sub(request):

    if request.method == "POST":

        merchant = request.POST.get("merchant")
        amount = request.POST.get("amount")
        date_due = request.POST.get("date_due")
        billing_period = request.POST.get("billing_period")
        category = request.POST.get("category")

        if not merchant or not amount or not date_due or not billing_period or not category:
            return render(
                request,
                "subscriptions/add_sub.html",
                {
                    "error": "Please fill in all fields."
                }
            )

        try:
            amount = Decimal(amount)

        except:
            return render(
                request,
                "subscriptions/add_sub.html",
                {
                    "error": "Please enter a valid amount."
                }
            )

        Subscription.objects.create(
            user=request.user,
            merchant=merchant,
            amount=amount,
            date_due=date_due,
            source="manual",
            billing_period=billing_period,
            category=category,
        )

        return redirect("dashboard")

    return render(
        request,
        "subscriptions/add_sub.html"
    )

@login_required
def remove_subscription(request, subscription_id):

    if request.method == "POST":

        subscription = get_object_or_404(
            Subscription,
            id=subscription_id,
            user=request.user
        )

        subscription.delete()

    return redirect("dashboard")

@login_required
def edit_subscription(request, sub_id):

    subscription = get_object_or_404(
        Subscription,
        id=sub_id,
        user=request.user
    )

    if request.method == "POST":
        merchant = request.POST.get("merchant")
        amount = request.POST.get("amount")
        due_date = request.POST.get("date_due")
        bill_period = request.POST.get("billing_period")
        category = request.POST.get("category")

        subscription.merchant = merchant.strip().capitalize()
        subscription.amount = Decimal(amount)
        subscription.date_due = due_date
        subscription.billing_period = bill_period
        subscription.category = category

        subscription.save()

        return redirect("dashboard")

    return render(
        request,
        "edit_sub.html",
        {
            "subscription": subscription
        }
    )

@login_required(login_url="login")
def delete_acc(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if request.method == "POST":
        user = request.user

        user_id = str(user.id)

        logout(request)
        user.delete()

        return redirect("home")

    return render(
        request,
        "subscriptions/delete_acc.html"
    )

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


@login_required(login_url="login")
def register(request):

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    request.session["google_oauth_state"] = state

    if flow.code_verifier:
        request.session["google_code_verifier"] = flow.code_verifier

    return redirect(authorization_url)

@login_required
def google_callback(request):

    state = request.session.get("google_oauth_state")
    code_verifier = request.session.get("google_code_verifier")

    if not state or not code_verifier:
        return redirect("register-gmail")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GMAIL_SCOPES,
        state=state,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
        code_verifier=code_verifier,
    )

    # Exchange Google's authorization code for credentials
    flow.fetch_token(
        authorization_response=request.build_absolute_uri()
    )

    credentials = flow.credentials

    # Connect to Gmail using the newly obtained credentials
    gmail_service = build(
        "gmail",
        "v1",
        credentials=credentials
    )

    # Get the Gmail account's email address
    profile = gmail_service.users().getProfile(
        userId="me"
    ).execute()

    google_email = profile["emailAddress"]

    # The existing logged-in SubTrack user
    user = request.user

    # Check whether this user already has a Google account connected
    google_account = GoogleAccount.objects.filter(
        user=user
    ).first()

    if google_account:

        google_account.google_email = google_email

        # Google may not return a refresh token when reconnecting.
        # Never overwrite a valid one with None.
        if credentials.refresh_token:
            google_account.refresh_token = credentials.refresh_token

        google_account.save()

    else:

        GoogleAccount.objects.create(
            user=user,
            google_email=google_email,
            refresh_token=credentials.refresh_token,
        )

    # Remove temporary OAuth data from the session
    request.session.pop("google_oauth_state", None)
    request.session.pop("google_code_verifier", None)
    request.session["gmail_verified"] = True

    return redirect("dashboard")

@login_required
def remove_gmail(request):
    if request.method == "POST":
        user = request.user

        google_acc = GoogleAccount.objects.filter(user=user).first()
        if google_acc:
            google_acc.delete()
            request.session["gmail_verified"] = False

        return redirect("home")
    return render(request, "subscriptions/delete_gmail.html")

@login_required
def user_settings(request):
    user = request.user
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        password = request.POST.get("password", "")
        
        if len(username) < 6:
            return render(request, "subscriptions/settings.html",
                {"error": "Username must be at least 6 characters long."}
            )
        if User.objects.filter(username=username).exclude(id=user.id).first():
            return render(request, "subscriptions/settings.html",
                          {"error":"Username is already taken"}
            )
        if User.objects.filter(email=email).exclude(id=user.id).first():
            return render(request, "subscriptions/settings.html",
                          {"error":"Email is already taken"}
            )
        user.name = name
        user.username = username
        user.email = email

        password_changed = False

        if password:
            if len(password) < 6:
                return render(
                    request,
                    "subscriptions/settings.html",
                    {"error": "Password must be at least 6 characters long."}
                )

            user.set_password(password)
            password_changed = True

        user.save()

        if password_changed:
            update_session_auth_hash(request, user)
        
        return render(request, "subscriptions/settings.html",
            {"success": "Settings saved successfully."}
        )
        
        

    return render(request, "subscriptions/settings.html")