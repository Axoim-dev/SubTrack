from .models import User, Subscription, GoogleAccount
import base64
import re
from decimal import Decimal
from email.utils import parseaddr
from dateutil import parser
from django.conf import settings
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


def get_gmail_service(google_account):
    credentials = Credentials(
        token=None,
        refresh_token=google_account.refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=GMAIL_SCOPES,
    )

    credentials.refresh(Request())

    return build(
        "gmail",
        "v1",
        credentials=credentials
    )


def decode_body(data):
    return base64.urlsafe_b64decode(
        data + "=" * (-len(data) % 4)
    ).decode(
        "utf-8",
        errors="ignore"
    )


def get_subscription_emails(service):
    result = service.users().messages().list(
        userId="me",
        q=(
            "in:inbox "
            "newer_than:3d "
            "(receipt OR payment OR invoice OR renewal "
            "OR subscription OR billing OR charged)"
        ),
        maxResults=100
    ).execute()

    return result.get("messages", [])


def extract_body(payload):
    body = payload.get("body", {})

    if body.get("data"):
        return decode_body(body["data"])

    for part in payload.get("parts", []):

        mime_type = part.get("mimeType", "")

        if mime_type == "text/plain":
            data = part.get("body", {}).get("data")

            if data:
                return decode_body(data)

        result = extract_body(part)

        if result:
            return result

    return ""


def get_email(service, message_id):
    return service.users().messages().get(
        userId="me",
        id=message_id,
        format="full"
    ).execute()


def extract_email_data(message):
    headers = message["payload"].get("headers", [])

    sender = ""
    subject = ""

    for header in headers:

        if header["name"].lower() == "from":
            sender = header["value"]

        elif header["name"].lower() == "subject":
            subject = header["value"]

    body = extract_body(
        message["payload"]
    )

    return sender, subject, body


def extract_merchant(sender):
    name, email = parseaddr(sender)

    if name:
        return name.strip()

    if email and "@" in email:
        domain = email.split("@")[1]
        return domain.split(".")[0].capitalize()

    return None


def extract_amount(text):
    patterns = [
        r'\$\s*(\d+(?:\.\d{2})?)',

        r'\b(?:AUD|USD|EUR|GBP)\s*'
        r'(\d+(?:\.\d{2})?)',

        r'(\d+(?:\.\d{2})?)\s*'
        r'(?:AUD|USD|EUR|GBP)\b',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return Decimal(
                match.group(1)
            )

    return None


def extract_due_date(text):
    patterns = [

        r'(?:next payment|next billing date|next charge)'
        r'.{0,80}?'
        r'([A-Za-z]+\s+\d{1,2},?\s+\d{4})',

        r'(?:renews|renewal)'
        r'.{0,50}?'
        r'([A-Za-z]+\s+\d{1,2},?\s+\d{4})',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL
        )

        if match:

            try:
                return parser.parse(
                    match.group(1)
                ).date()

            except (ValueError, OverflowError):
                pass

    return None


def extract_billing_period(text):
    text = text.lower()

    if any(x in text for x in [
        "weekly",
        "every week",
        "per week"
    ]):
        return "weekly"

    if any(x in text for x in [
        "monthly",
        "every month",
        "per month"
    ]):
        return "monthly"

    if any(x in text for x in [
        "yearly",
        "annual",
        "annually",
        "every year",
        "per year"
    ]):
        return "yearly"

    return None


def extract_category(text):
    text = text.lower()

    categories = {

        "entertainment": [
            "streaming",
            "movie",
            "television",
            "tv"
        ],

        "music": [
            "music",
            "audio"
        ],

        "software": [
            "software",
            "license",
            "application",
            "cloud"
        ],

        "gaming": [
            "gaming",
            "game",
            "console"
        ],

        "education": [
            "course",
            "education",
            "learning"
        ],

        "fitness": [
            "fitness",
            "gym"
        ],

        "shopping": [
            "shopping",
            "store"
        ],
    }

    for category, keywords in categories.items():

        if any(
            keyword in text
            for keyword in keywords
        ):
            return category

    return "other"


def validate_subscription(data):
    return all([
        data["merchant"] is not None,
        data["amount"] is not None,
        data["date_due"] is not None,
        data["billing_period"] is not None,
    ])


def save_subscription(
    user,
    google_account,
    data,
    message_id
):

    if Subscription.objects.filter(
        google_account=google_account,
        gmail_message_id=message_id
    ).exists():
        return

    Subscription.objects.create(
        user=user,
        google_account=google_account,
        merchant=data["merchant"],
        amount=data["amount"],
        date_due=data["date_due"],
        billing_period=data["billing_period"],
        category=data["category"],
        source="gmail",
        gmail_message_id=message_id,
    )



def background_sync(google_account):

    user = google_account.user


    service = get_gmail_service(
        google_account
    )

    messages = get_subscription_emails(
        service
    )


    for message in messages:

        message_id = message["id"]

        full_message = get_email(
            service,
            message_id
        )

        labels = full_message.get(
            "labelIds",
            []
        )

        if "TRASH" in labels:
            continue

        if "SPAM" in labels:
            continue

        if Subscription.objects.filter(
            google_account=google_account,
            gmail_message_id=message_id
        ).exists():
            print(f"ALREADY EXISTS: {message_id}")
            continue

        sender, subject, body = extract_email_data(
            full_message
        )

        text = f"{subject}\n{body}"

        data = {
            "merchant": extract_merchant(sender),
            "amount": extract_amount(text),
            "date_due": extract_due_date(text),
            "billing_period": extract_billing_period(text),
            "category": extract_category(text),
        }


        if not validate_subscription(data):
            print("INVALID SUBSCRIPTION, SKIPPING")
            continue

        save_subscription(
            user,
            google_account,
            data,
            message_id
        )

        print(f"SAVED: {data['merchant']}")

    print("SYNC FINISHED")