# SubTrack

SubTrack is a Django-based subscription tracker that helps users keep track of recurring subscriptions, spending, and upcoming payments.

It supports both manually added subscriptions and automatic subscription detection through Gmail.

## Features

- User registration and authentication
- Add and manage subscriptions
- Monthly, weekly, and yearly billing periods
- Subscription categories
- Dashboard showing subscription information and spending
- Spending analytics
- Google Gmail integration
- Automatic detection of subscription emails
- Automatic recurring subscription due-date updates
- Background processing with Celery
- Redis/Memurai task queue support
- PostgreSQL support for production deployments

## Tech Stack

- Python
- Django
- PostgreSQL
- Celery
- Redis
- Google Gmail API
- Google OAuth 2.0
- HTML/CSS/JavaScript

## Project Structure

```text
SubTrack/
├── config/
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   └── ...
│
├── subscriptions/
│   ├── models.py
│   ├── views.py
│   ├── tasks.py
│   ├── gmail.py
│   ├── urls.py
│   ├── templates/
│   └── static/
│
├── manage.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd SubTrack
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```powershell
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file based on `.env.example`:

```text
.env.example → .env
```

Fill in the required environment variables with your own values.

## Environment Variables

The project uses environment variables for sensitive configuration.

Example:

```env
SECRET_KEY=put-your-django-secret-key-here
DEBUG=False

GOOGLE_CLIENT_ID=put-your-google-client-id-here
GOOGLE_CLIENT_SECRET=put-your-google-client-secret-here
GOOGLE_REDIRECT_URI=put-your-google-oauth-callback-url-here

DATABASE_URL=put-your-postgres-database-url-here

CELERY_BROKER_URL=put-your-redis-url-here

ALLOWED_HOSTS=put-your-domain-here
```

Never commit your `.env` file to GitHub.

## Database

SubTrack can use SQLite during development and PostgreSQL in production.

For a Railway deployment, set the `DATABASE_URL` environment variable to the PostgreSQL connection URL provided by Railway.

Run migrations:

```bash
python manage.py migrate
```

Create an admin account if needed:

```bash
python manage.py createsuperuser
```

## Google Gmail Integration

SubTrack uses Google OAuth 2.0 to connect a user's Gmail account.

The Gmail integration uses the read-only Gmail API scope and scans recent relevant emails to identify potential subscription payments and renewals.

The Google OAuth callback URL must match the redirect URI configured in Google Cloud.

For local development:

```text
http://127.0.0.1:8000/google/callback/
```

For production, use your deployed HTTPS domain.

## Celery

Celery handles background tasks so Gmail scanning and subscription maintenance do not need to run during normal Django requests.

SubTrack uses separate queues for different workloads:

```text
Redis
 ├── gmail queue
 │      └── Gmail worker
 │
 └── subscriptions queue
        └── Subscription worker
```

Start the Gmail worker:

```bash
celery -A config worker -l info -P solo -Q gmail -n gmail_worker
```

Start the subscription worker:

```bash
celery -A config worker -l info -P solo -Q subscriptions -n subscriptions_worker
```

Start Celery Beat:

```bash
celery -A config beat -l info
```

Celery Beat schedules recurring tasks such as Gmail synchronization and subscription due-date updates.

## Gmail Scanning

The Gmail integration searches recent relevant emails and attempts to extract:

- Merchant
- Amount
- Next payment date
- Billing period
- Subscription category

Detected subscriptions are saved with their Gmail message ID to prevent the same email from creating duplicate subscriptions.

## Production

For production deployment, the application requires:

- Django application server
- PostgreSQL database
- Redis
- Celery worker for Gmail tasks
- Celery worker for subscription tasks
- Celery Beat scheduler

The Django server, Celery workers, and Celery Beat should be configured as persistent services so they automatically start and restart when necessary.

## Development

Start Django:

```bash
python manage.py runserver
```

Start the Gmail worker:

```bash
celery -A config worker -l info -P solo -Q gmail -n gmail_worker
```

Start the subscription worker:

```bash
celery -A config worker -l info -P solo -Q subscriptions -n subscriptions_worker
```

Start Beat:

```bash
celery -A config beat -l info
```

Redis must also be running.

## Security

Sensitive configuration should never be committed to the repository.

The following should remain private:

- Django `SECRET_KEY`
- Google OAuth client secret
- Database credentials
- Redis credentials
- Production environment variables

The `.env` file is excluded using `.gitignore`.

## Status

SubTrack is currently under development.

More features and improvements are planned as the project continues to develop.
