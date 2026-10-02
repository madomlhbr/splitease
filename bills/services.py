"""Money logic: splitting, balances, and debt simplification. All amounts are integer centavos."""
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP


class SplitError(ValueError):
    pass


def to_cents(value):
    return int((Decimal(value) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def allocate(total, weights):
    """Split `total` centavos by weight using the largest-remainder method.

    Shares always add up to `total` exactly; leftover centavos go to the largest
    fractional remainders, ties broken by key so results are deterministic.
    """
    if not weights:
        raise SplitError("Select at least one person to split with.")
    weight_sum = sum(Decimal(w) for w in weights.values())
    if weight_sum <= 0:
        raise SplitError("Values must add up to more than zero.")
    base, remainders = {}, {}
    for key, w in weights.items():
        quotient, remainder = divmod(Decimal(total) * Decimal(w), weight_sum)
        base[key], remainders[key] = int(quotient), remainder
    leftover = total - sum(base.values())
    for key in sorted(weights, key=lambda k: (-remainders[k], k))[:leftover]:
        base[key] += 1
    return base


def compute_shares(split_type, total_cents, values):
    """`values` maps user_id -> weight (equal: ignored, percent, shares) or pesos (exact)."""
    if split_type == "equal":
        return allocate(total_cents, {k: 1 for k in values})
    if split_type == "percent":
        if sum(Decimal(v) for v in values.values()) != 100:
            raise SplitError("Percentages must add up to 100.")
        return allocate(total_cents, values)
    if split_type == "shares":
        return allocate(total_cents, values)
    if split_type == "exact":
        cents = {k: to_cents(v) for k, v in values.items()}
        if sum(cents.values()) != total_cents:
            raise SplitError("Exact amounts must add up to the total.")
        return cents
    raise SplitError("Unknown split type.")


def net_balances(group):
    """user_id -> centavos. Positive: the group owes them. Negative: they owe the group."""
    net = defaultdict(int)
    for m in group.members.all():
        net[m.pk] += 0
    for e in group.expenses.prefetch_related("shares"):
        net[e.paid_by_id] += e.amount_cents
        for s in e.shares.all():
            net[s.user_id] -= s.amount_cents
    for s in group.settlements.all():
        net[s.payer_id] += s.amount_cents
        net[s.payee_id] -= s.amount_cents
    return dict(net)


def simplify(net):
    """Greedy debt simplification: repeatedly match the biggest debtor to the biggest creditor.

    Returns [(payer_id, payee_id, cents)] with at most (people - 1) payments.
    """
    debtors = [[u, -a] for u, a in net.items() if a < 0]
    creditors = [[u, a] for u, a in net.items() if a > 0]
    payments = []
    while debtors and creditors:
        debtors.sort(key=lambda x: (-x[1], x[0]))
        creditors.sort(key=lambda x: (-x[1], x[0]))
        d, c = debtors[0], creditors[0]
        amount = min(d[1], c[1])
        payments.append((d[0], c[0], amount))
        d[1] -= amount
        c[1] -= amount
        debtors = [x for x in debtors if x[1]]
        creditors = [x for x in creditors if x[1]]
    return payments


def is_guest(user):
    return hasattr(user, "guest_profile")


def display_name(user):
    return user.guest_profile.name if is_guest(user) else user.username
