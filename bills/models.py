import secrets
from datetime import date
from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


def make_code():
    return secrets.token_urlsafe(6)


class Group(models.Model):
    name = models.CharField(max_length=80)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="owned_groups")
    members = models.ManyToManyField(User, related_name="split_groups")
    invite_code = models.CharField(max_length=16, unique=True, default=make_code)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Expense(models.Model):
    SPLIT_CHOICES = [("equal", "Equally"), ("exact", "Exact amounts"),
                     ("percent", "Percentages"), ("shares", "Shares")]
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="expenses")
    description = models.CharField(max_length=120)
    amount_cents = models.PositiveBigIntegerField()  # money is stored as integer centavos
    paid_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    split_type = models.CharField(max_length=10, choices=SPLIT_CHOICES, default="equal")
    date = models.DateField(default=date.today)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-id"]


class Share(models.Model):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="shares")
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    amount_cents = models.PositiveBigIntegerField()


class Settlement(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="settlements")
    payer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    payee = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    amount_cents = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Guest(models.Model):
    """A person added to a group without an account. Backed by an inactive User row
    so balances, splits, and settlements treat them like any other member."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="guest_profile")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="guests")
    name = models.CharField(max_length=40)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
