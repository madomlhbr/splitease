from django.contrib import admin
from .models import Expense, Group, Guest, Settlement, Share

admin.site.register([Group, Expense, Share, Settlement, Guest])
