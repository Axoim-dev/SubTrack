from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class User(AbstractUser):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    name = models.CharField(max_length=200)

    email = models.EmailField(
        max_length=100,
        unique=True
    )

class GoogleAccount(models.Model):

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="google_account"
    )

    google_email = models.EmailField(unique=True)

    refresh_token = models.TextField()

    connected_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.google_email

class Subscription(models.Model):

    CATEGORY_CHOICES = [
        ("entertainment", "Entertainment"),
        ("software", "Software"),
        ("music", "Music"),
        ("gaming", "Gaming"),
        ("education", "Education"),
        ("fitness", "Fitness"),
        ("shopping", "Shopping"),
        ("other", "Other"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="subscriptions"
    )

    google_account = models.ForeignKey(
        GoogleAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions"
    )

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    merchant = models.CharField(max_length=200)

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    date_due = models.DateField()

    source = models.CharField(
        max_length=20,
        choices=[
            ("manual", "Manual"),
            ("gmail", "Gmail"),
        ],
        default="manual"
    )

    billing_period = models.CharField(
        max_length=20,
        choices=[
            ("weekly", "Weekly"),
            ("monthly", "Monthly"),
            ("yearly", "Yearly"),
        ],
        default="monthly"
    )

    category = models.CharField(
        max_length=30,
        choices=CATEGORY_CHOICES,
        default="other"
    )

    gmail_message_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["google_account", "gmail_message_id"],
                name="unique_google_message"
            )
        ]

class EmailVerificationCode(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()