from .models import User, Subscription, GoogleAccount

import base64
import html
import re

from decimal import Decimal, InvalidOperation
from email.utils import parseaddr
from datetime import date, timedelta

from dateutil import parser
from dateutil.relativedelta import relativedelta

from django.conf import settings

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


# ============================================================
# GMAIL SERVICE
# ============================================================

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
        credentials=credentials,
    )


# ============================================================
# DECODING
# ============================================================

def decode_body(data):
    if not data:
        return ""

    try:
        decoded = base64.urlsafe_b64decode(
            data + "=" * (-len(data) % 4)
        )

        return decoded.decode(
            "utf-8",
            errors="ignore",
        )

    except Exception:
        return ""


def html_to_text(value):
    """
    Converts HTML email into reasonably clean text.

    Handles:
    - HTML tags
    - HTML entities
    - excessive whitespace
    - line breaks
    """

    if not value:
        return ""

    value = html.unescape(value)

    # Turn common block elements into newlines
    value = re.sub(
        r"<\s*(br|p|div|tr|li|h[1-6])[^>]*>",
        "\n",
        value,
        flags=re.IGNORECASE,
    )

    # Remove remaining HTML
    value = re.sub(
        r"<[^>]+>",
        " ",
        value,
    )

    # Decode entities again in case some were nested
    value = html.unescape(value)

    # Normalize whitespace
    value = re.sub(
        r"[ \t]+",
        " ",
        value,
    )

    value = re.sub(
        r"\n\s*\n+",
        "\n",
        value,
    )

    return value.strip()


# ============================================================
# EMAIL BODY
# ============================================================

def extract_body(payload):
    """
    Prefer text/plain, but fall back to HTML.

    Real emails are messy because apparently everyone agreed
    that sending HTML tables inside emails was a good idea.
    """

    plain_parts = []
    html_parts = []

    body = payload.get("body", {})

    if body.get("data"):
        mime_type = payload.get("mimeType", "")

        decoded = decode_body(body["data"])

        if mime_type == "text/plain":
            plain_parts.append(decoded)

        elif mime_type == "text/html":
            html_parts.append(decoded)

    for part in payload.get("parts", []):
        mime_type = part.get("mimeType", "").lower()

        data = part.get("body", {}).get("data")

        if data:
            decoded = decode_body(data)

            if mime_type == "text/plain":
                plain_parts.append(decoded)

            elif mime_type == "text/html":
                html_parts.append(decoded)

        # Multipart emails can be nested
        nested = extract_body(part)

        if nested:
            plain_parts.append(nested)

    # Plain text is preferable
    if plain_parts:
        return "\n".join(plain_parts).strip()

    if html_parts:
        return html_to_text(
            "\n".join(html_parts)
        )

    return ""


# ============================================================
# EMAIL RETRIEVAL
# ============================================================

def get_subscription_emails(service):
    """
    Search for likely subscription/payment emails.

    We intentionally don't require every email to contain
    'subscription'. Lots of companies use 'receipt',
    'order', 'payment', 'renewed', etc.
    """

    queries = [
        (
            "in:inbox newer_than:30d "
            "(subscription OR renewal OR renewed OR "
            "billing OR payment OR receipt OR invoice OR "
            "charged OR charge OR membership OR plan)"
        ),

        (
            "in:inbox newer_than:30d "
            "(recurring OR recurring payment OR "
            "monthly OR yearly OR annual OR weekly)"
        ),
    ]

    messages = {}

    for query in queries:
        result = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=100,
        ).execute()

        for message in result.get("messages", []):
            messages[message["id"]] = message

    return list(messages.values())


# ============================================================
# FULL EMAIL
# ============================================================

def get_email(service, message_id):
    return service.users().messages().get(
        userId="me",
        id=message_id,
        format="full",
    ).execute()


def extract_email_data(message):
    headers = message["payload"].get(
        "headers",
        []
    )

    sender = ""
    subject = ""

    for header in headers:
        name = header.get("name", "").lower()
        value = header.get("value", "")

        if name == "from":
            sender = value

        elif name == "subject":
            subject = value

    body = extract_body(
        message["payload"]
    )

    return sender, subject, body


# ============================================================
# MERCHANT
# ============================================================

def extract_merchant(sender):
    name, email = parseaddr(sender)

    if name:
        # Remove weird quotation marks
        name = name.strip().strip('"').strip("'")

        # Avoid useless generic names
        if name.lower() not in {
            "no reply",
            "noreply",
            "billing",
            "support",
            "notifications",
            "notification",
        }:
            return name

    if email and "@" in email:
        domain = email.split("@", 1)[1].lower()

        # Remove common mail subdomains
        domain = re.sub(
            r"^(mail|email|billing|support|no-reply|noreply)\.",
            "",
            domain,
        )

        company = domain.split(".")[0]

        if company:
            return company.replace(
                "-", " "
            ).title()

    return None


# ============================================================
# AMOUNT
# ============================================================

def extract_amount(text):
    """
    Handles examples such as:

    $15.99
    A$15.99
    AU$15.99
    AUD 15.99
    15.99 AUD
    €9.99
    EUR 9.99
    £10.00
    GBP 10.00
    $1,299.99
    15,99 EUR
    """

    if not text:
        return None

    patterns = [

        # A$15.99 / AU$15.99 / AUD $15.99
        r'\b(?:AU\$|A\$|AUD\s*\$?)\s*'
        r'(\d[\d,]*(?:[.,]\d{1,2})?)',

        # $15.99 AUD
        r'(?:\$)\s*'
        r'(\d[\d,]*(?:[.,]\d{1,2})?)'
        r'\s*(?:AUD|USD|CAD|NZD)',

        # AUD 15.99
        r'\b(?:AUD|USD|CAD|NZD|EUR|GBP)\s*'
        r'(\d[\d,]*(?:[.,]\d{1,2})?)',

        # 15.99 AUD
        r'\b(\d[\d,]*(?:[.,]\d{1,2})?)\s*'
        r'(?:AUD|USD|CAD|NZD|EUR|GBP)\b',

        # €15.99
        r'[€£]\s*'
        r'(\d[\d,]*(?:[.,]\d{1,2})?)',

        # Generic $
        r'\$\s*'
        r'(\d[\d,]*(?:[.,]\d{1,2})?)',
    ]

    # Prefer amounts near billing-related words
    priority_patterns = [
        r'(?:amount charged|amount paid|total|price|'
        r'subscription fee|membership fee|recurring fee)'
        r'.{0,40}?'
        r'(?:A\$|AU\$|AUD\s*\$?|\$|AUD|USD|EUR|GBP|€|£)'
        r'\s*'
        r'(\d[\d,]*(?:[.,]\d{1,2})?)',
    ]

    for pattern in priority_patterns + patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL,
        )

        if not match:
            continue

        value = match.group(1)

        try:
            # Handle:
            # 1,299.99 -> 1299.99
            # 15,99 -> 15.99
            if "," in value and "." in value:
                value = value.replace(",", "")

            elif "," in value:
                parts = value.split(",")

                if (
                    len(parts[-1]) == 2
                ):
                    value = value.replace(
                        ",",
                        ".",
                    )
                else:
                    value = value.replace(
                        ",",
                        "",
                    )

            return Decimal(value)

        except InvalidOperation:
            continue

    return None


# ============================================================
# DATE EXTRACTION
# ============================================================

DATE_PATTERNS = [

    # ----------------------------------------
    # Explicit next-payment language
    # ----------------------------------------

    r'(?:next payment|next billing date|next billing|'
    r'next charge|next payment date|next renewal|'
    r'payment date|billing date)'
    r'.{0,100}?'
    r'([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})',

    r'(?:next payment|next billing date|next billing|'
    r'next charge|next payment date|next renewal|'
    r'payment date|billing date)'
    r'.{0,100}?'
    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',

    r'(?:next payment|next billing date|next billing|'
    r'next charge|next payment date|next renewal|'
    r'payment date|billing date)'
    r'.{0,100}?'
    r'(\d{4}-\d{1,2}-\d{1,2})',

    # ----------------------------------------
    # Renewal language
    # ----------------------------------------

    r'(?:renews|renewal|renewing|renewed on|'
    r'renewal date|renewal occurs)'
    r'.{0,100}?'
    r'([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})',

    r'(?:renews|renewal|renewing|renewed on|'
    r'renewal date|renewal occurs)'
    r'.{0,100}?'
    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',

    r'(?:renews|renewal|renewing|renewed on|'
    r'renewal date|renewal occurs)'
    r'.{0,100}?'
    r'(\d{4}-\d{1,2}-\d{1,2})',

    # ----------------------------------------
    # "Due" language
    # ----------------------------------------

    r'(?:due|due on|due date|payable by)'
    r'.{0,60}?'
    r'([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})',

    r'(?:due|due on|due date|payable by)'
    r'.{0,60}?'
    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',

    r'(?:due|due on|due date|payable by)'
    r'.{0,60}?'
    r'(\d{4}-\d{1,2}-\d{1,2})',

    # ----------------------------------------
    # "will be charged on"
    # ----------------------------------------

    r'(?:will be charged|will charge you|'
    r'charged again|charge will occur)'
    r'.{0,100}?'
    r'([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})',

    r'(?:will be charged|will charge you|'
    r'charged again|charge will occur)'
    r'.{0,100}?'
    r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',

    # ----------------------------------------
    # "on October 15"
    # ----------------------------------------

    r'(?:subscription|plan|membership)'
    r'.{0,100}?'
    r'(?:on|until)\s+'
    r'([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})',
]


def parse_date_value(date_text):
    if not date_text:
        return None

    date_text = date_text.strip()

    try:
        # DD/MM/YYYY
        if re.match(
            r'^\d{1,2}/\d{1,2}/\d{2,4}$',
            date_text,
        ):
            return parser.parse(
                date_text,
                dayfirst=True,
            ).date()

        # DD-MM-YYYY
        if re.match(
            r'^\d{1,2}-\d{1,2}-\d{2,4}$',
            date_text,
        ):
            return parser.parse(
                date_text,
                dayfirst=True,
            ).date()

        # ISO
        if re.match(
            r'^\d{4}-\d{1,2}-\d{1,2}$',
            date_text,
        ):
            return parser.parse(
                date_text,
            ).date()

        # Written date
        return parser.parse(
            date_text,
            dayfirst=True,
        ).date()

    except (
        ValueError,
        OverflowError,
        TypeError,
    ):
        return None


def extract_due_date(text):
    if not text:
        return None

    for pattern in DATE_PATTERNS:

        matches = re.finditer(
            pattern,
            text,
            re.IGNORECASE | re.DOTALL,
        )

        for match in matches:
            date_text = match.group(1)

            result = parse_date_value(
                date_text
            )

            if result:
                return result

    return None


# ============================================================
# BILLING PERIOD
# ============================================================

def extract_billing_period(text):
    text = text.lower()

    weekly_patterns = [
        "weekly",
        "every week",
        "per week",
        "each week",
        "week-to-week",
        "7 days",
    ]

    monthly_patterns = [
        "monthly",
        "every month",
        "per month",
        "each month",
        "once a month",
        "every 30 days",
        "30-day",
    ]

    yearly_patterns = [
        "yearly",
        "annual",
        "annually",
        "every year",
        "per year",
        "each year",
        "once a year",
        "12 months",
        "365 days",
    ]

    for phrase in weekly_patterns:
        if phrase in text:
            return "weekly"

    for phrase in monthly_patterns:
        if phrase in text:
            return "monthly"

    for phrase in yearly_patterns:
        if phrase in text:
            return "yearly"

    # "billed every 3 months" isn't supported by your model,
    # so don't pretend it's monthly.
    if re.search(
        r'every\s+3\s+months|quarterly',
        text,
    ):
        return "monthly"

    return None


# ============================================================
# CATEGORY
# ============================================================

CATEGORY_KEYWORDS = {

    "entertainment": [
        "netflix",
        "disney",
        "hulu",
        "streaming",
        "movie",
        "television",
        "tv",
        "video",
        "paramount",
        "prime video",
    ],

    "music": [
        "spotify",
        "apple music",
        "youtube music",
        "tidal",
        "music",
        "audio",
        "soundcloud",
    ],

    "software": [
        "adobe",
        "microsoft 365",
        "office 365",
        "dropbox",
        "notion",
        "software",
        "license",
        "application",
        "app",
        "cloud",
        "storage",
        "github",
        "jetbrains",
    ],

    "gaming": [
        "xbox",
        "game pass",
        "playstation",
        "ps plus",
        "nintendo",
        "steam",
        "gaming",
        "game",
        "console",
    ],

    "education": [
        "course",
        "education",
        "learning",
        "school",
        "university",
        "udemy",
        "coursera",
        "skillshare",
    ],

    "fitness": [
        "fitness",
        "gym",
        "workout",
        "membership",
        "health club",
    ],

    "shopping": [
        "shopping",
        "store",
        "amazon",
        "walmart",
        "ebay",
        "retail",
    ],
}


def extract_category(text):
    text = text.lower()

    scores = {
        category: 0
        for category in CATEGORY_KEYWORDS
    }

    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:

            if keyword in text:
                # Merchant-specific terms get a little more weight
                if keyword in {
                    "spotify",
                    "netflix",
                    "xbox",
                    "steam",
                    "adobe",
                    "dropbox",
                    "github",
                    "playstation",
                    "nintendo",
                }:
                    scores[category] += 3
                else:
                    scores[category] += 1

    best_category = max(
        scores,
        key=scores.get,
    )

    if scores[best_category] == 0:
        return "other"

    return best_category


# ============================================================
# SUBSCRIPTION VALIDATION
# ============================================================

def validate_subscription(data):
    return all([
        data.get("merchant") is not None,
        data.get("amount") is not None,
        data.get("date_due") is not None,
        data.get("billing_period") is not None,
    ])


# ============================================================
# SAVE
# ============================================================

def save_subscription(
    user,
    google_account,
    data,
    message_id,
):

    if Subscription.objects.filter(
        google_account=google_account,
        gmail_message_id=message_id,
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


# ============================================================
# BACKGROUND SYNC
# ============================================================

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
            message_id,
        )

        labels = full_message.get(
            "labelIds",
            [],
        )

        if "TRASH" in labels:
            continue

        if "SPAM" in labels:
            continue

        if Subscription.objects.filter(
            google_account=google_account,
            gmail_message_id=message_id,
        ).exists():

            print(
                f"ALREADY EXISTS: {message_id}"
            )

            continue

        sender, subject, body = extract_email_data(
            full_message
        )

        # Subject is important because some HTML emails
        # contain almost no useful text in their body.
        text = f"{subject}\n{body}"

        data = {
            "merchant": extract_merchant(
                sender
            ),

            "amount": extract_amount(
                text
            ),

            "date_due": extract_due_date(
                text
            ),

            "billing_period": extract_billing_period(
                text
            ),

            "category": extract_category(
                text
            ),
        }

        print(
            f"PARSED: {data}"
        )

        if not validate_subscription(data):

            print(
                "INVALID SUBSCRIPTION, SKIPPING"
            )

            continue

        save_subscription(
            user,
            google_account,
            data,
            message_id,
        )

        print(
            f"SAVED: {data['merchant']}"
        )

    print("SYNC FINISHED")