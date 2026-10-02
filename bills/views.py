import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import ExpenseForm, GroupForm
from .models import Expense, Group, Guest, Settlement, Share
from .services import is_guest, net_balances, simplify, to_cents

User = get_user_model()


def signup(request):
    form = UserCreationForm(request.POST or None)
    if form.is_valid():
        login(request, form.save())
        return redirect("group_list")
    return render(request, "registration/signup.html", {"form": form})


def _group_for(request, pk):
    return get_object_or_404(request.user.split_groups, pk=pk)


@login_required
def group_list(request):
    form = GroupForm(request.POST or None)
    if form.is_valid():
        group = form.save(commit=False)
        group.owner = request.user
        group.save()
        group.members.add(request.user)
        return redirect("group_detail", pk=group.pk)
    return render(request, "group_list.html", {"groups": request.user.split_groups.all(), "form": form})


@login_required
def join_group(request, code):
    group = get_object_or_404(Group, invite_code=code)
    group.members.add(request.user)
    messages.success(request, f"You joined {group.name}.")
    return redirect("group_detail", pk=group.pk)


@login_required
def group_detail(request, pk):
    group = _group_for(request, pk)
    members = {m.pk: m for m in group.members.all()}
    net = net_balances(group)
    context = {
        "group": group,
        "balances": sorted(((members.get(u), a) for u, a in net.items() if u in members),
                           key=lambda r: -r[1]),
        "suggestions": [(members[p], members[r], a) for p, r, a in simplify(net)
                        if p in members and r in members],
        "expenses": group.expenses.select_related("paid_by").prefetch_related("shares__user"),
        "settlements": group.settlements.select_related("payer", "payee")[:10],
        "invite_url": request.build_absolute_uri(f"/join/{group.invite_code}/"),
        "me": net.get(request.user.pk, 0),
    }
    return render(request, "group_detail.html", context)


@login_required
def add_expense(request, pk):
    group = _group_for(request, pk)
    form = ExpenseForm(request.POST or None, members=group.members.order_by("username"),
                       initial={"paid_by": request.user})
    if form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            expense = Expense.objects.create(
                group=group, description=d["description"], amount_cents=to_cents(d["amount"]),
                paid_by=d["paid_by"], split_type=d["split_type"], date=d["date"])
            Share.objects.bulk_create(
                Share(expense=expense, user_id=uid, amount_cents=c)
                for uid, c in form.shares.items() if c > 0)
        return redirect("group_detail", pk=group.pk)
    return render(request, "expense_form.html", {"group": group, "form": form})


@login_required
@require_POST
def delete_expense(request, pk, expense_id):
    group = _group_for(request, pk)
    expense = get_object_or_404(group.expenses, pk=expense_id)
    if request.user in (expense.paid_by, group.owner) or is_guest(expense.paid_by):
        expense.delete()
    else:
        messages.error(request, "Only the payer or the group owner can delete an expense.")
    return redirect("group_detail", pk=group.pk)


@login_required
@require_POST
def settle(request, pk):
    group = _group_for(request, pk)
    payer = get_object_or_404(group.members, pk=request.POST.get("payer"))
    payee = get_object_or_404(group.members, pk=request.POST.get("payee"))
    try:
        cents = int(request.POST["cents"])
    except (KeyError, ValueError):
        cents = 0
    involved = request.user in (payer, payee) or is_guest(payer) or is_guest(payee)
    if not involved or payer == payee or cents <= 0:
        messages.error(request, "That payment couldn't be recorded.")
    else:
        Settlement.objects.create(group=group, payer=payer, payee=payee, amount_cents=cents)
    return redirect("group_detail", pk=group.pk)


@login_required
@require_POST
def add_guest(request, pk):
    group = _group_for(request, pk)
    name = request.POST.get("name", "").strip()[:40]
    if not name:
        messages.error(request, "Enter a name to add someone.")
    else:
        user = User.objects.create_user(f"guest-{secrets.token_hex(5)}", is_active=False)
        Guest.objects.create(user=user, group=group, name=name, created_by=request.user)
        group.members.add(user)
        messages.success(request, f"{name} was added. They don't need an account.")
    return redirect("group_detail", pk=group.pk)
