from datetime import date
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from .models import Expense, Group
from .services import SplitError, compute_shares, display_name, to_cents

User = get_user_model()


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ["name"]
        widgets = {"name": forms.TextInput(attrs={"placeholder": "e.g. Baguio trip"})}


class ExpenseForm(forms.Form):
    description = forms.CharField(max_length=120)
    amount = forms.DecimalField(min_value=Decimal("0.01"), max_digits=12, decimal_places=2)
    paid_by = forms.ModelChoiceField(queryset=User.objects.none())
    split_type = forms.ChoiceField(choices=Expense.SPLIT_CHOICES)
    date = forms.DateField(initial=date.today, widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, members, **kwargs):
        super().__init__(*args, **kwargs)
        self.members = list(members)
        self.fields["paid_by"].queryset = User.objects.filter(pk__in=[m.pk for m in self.members])
        self.fields["paid_by"].label_from_instance = display_name
        self.member_rows = []
        for m in self.members:
            inc = forms.BooleanField(required=False, initial=True)
            val = forms.DecimalField(required=False, min_value=0, max_digits=12, decimal_places=2)
            self.fields[f"inc_{m.pk}"], self.fields[f"val_{m.pk}"] = inc, val
            self.member_rows.append((m, self[f"inc_{m.pk}"], self[f"val_{m.pk}"]))

    def clean(self):
        data = super().clean()
        if self.errors:
            return data
        included = [m for m in self.members if data.get(f"inc_{m.pk}")]
        values = {m.pk: data.get(f"val_{m.pk}") or Decimal(0) for m in included}
        try:
            self.shares = compute_shares(data["split_type"], to_cents(data["amount"]), values)
        except SplitError as exc:
            raise forms.ValidationError(str(exc))
        return data
