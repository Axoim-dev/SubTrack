from celery import shared_task
from subscriptions.models import GoogleAccount, Subscription
from subscriptions.gmail import background_sync
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta


@shared_task(queue="gmail")
def sync_google_account(google_account_id):

    google_account = GoogleAccount.objects.filter(
        id=google_account_id
    ).first()

    if not google_account:
        print(
            f"GoogleAccount {google_account_id} no longer exists. "
            "Skipping sync."
        )
        return

    background_sync(google_account)


@shared_task(queue="gmail")
def queue_gmail_syncs():

    accounts = GoogleAccount.objects.all()

    for account in accounts:
        sync_google_account.delay(account.id)


@shared_task(queue="subscriptions")
def update_due_dates():

    today = date.today()

    subscriptions = Subscription.objects.filter(
        date_due__lte=today
    )

    for sub in subscriptions:

        while sub.date_due <= today:

            if sub.billing_period == "weekly":
                sub.date_due += timedelta(days=7)

            elif sub.billing_period == "monthly":
                sub.date_due += relativedelta(months=1)

            elif sub.billing_period == "yearly":
                sub.date_due += relativedelta(years=1)

            else:
                break

        sub.save(update_fields=["date_due"])