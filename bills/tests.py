from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from .models import Group
from .services import SplitError, allocate, compute_shares, net_balances, simplify

User = get_user_model()


class SplitTests(TestCase):
    def test_equal_split_distributes_leftover_centavo(self):
        shares = compute_shares("equal", 10000, {1: 0, 2: 0, 3: 0})
        self.assertEqual(sorted(shares.values()), [3333, 3333, 3334])
        self.assertEqual(sum(shares.values()), 10000)

    def test_percent_must_total_100(self):
        with self.assertRaises(SplitError):
            compute_shares("percent", 10000, {1: 60, 2: 30})
        self.assertEqual(compute_shares("percent", 10000, {1: 60, 2: 40}), {1: 6000, 2: 4000})

    def test_shares_are_weighted(self):
        self.assertEqual(compute_shares("shares", 9000, {1: 2, 2: 1}), {1: 6000, 2: 3000})

    def test_exact_must_match_total(self):
        with self.assertRaises(SplitError):
            compute_shares("exact", 10000, {1: "40", 2: "50"})
        self.assertEqual(compute_shares("exact", 10000, {1: "40", 2: "60"}), {1: 4000, 2: 6000})

    def test_allocate_always_sums_to_total(self):
        for total in (1, 99, 1001, 12345):
            self.assertEqual(sum(allocate(total, {1: 1, 2: 1, 3: 1, 4: 7}).values()), total)

    def test_no_participants_rejected(self):
        with self.assertRaises(SplitError):
            compute_shares("equal", 100, {})


class SimplifyTests(TestCase):
    def test_chain_collapses_to_one_payment(self):
        # A owes B 100, B owes C 100  ->  net: A -100, B 0, C +100
        self.assertEqual(simplify({1: -10000, 2: 0, 3: 10000}), [(1, 3, 10000)])

    def test_payments_clear_every_balance(self):
        net = {1: -7000, 2: -3000, 3: 4000, 4: 6000}
        left = dict(net)
        for payer, payee, amount in simplify(net):
            left[payer] += amount
            left[payee] -= amount
        self.assertTrue(all(v == 0 for v in left.values()))
        self.assertLessEqual(len(simplify(net)), 3)


class FlowTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("ana", password="pw12345!")
        self.b = User.objects.create_user("ben", password="pw12345!")
        self.group = Group.objects.create(name="Trip", owner=self.a)
        self.group.members.add(self.a, self.b)
        self.client.force_login(self.a)

    def post_expense(self, **extra):
        data = {"description": "Dinner", "amount": "300.00", "paid_by": self.a.pk,
                "split_type": "equal", "date": "2026-10-02",
                f"inc_{self.a.pk}": "on", f"inc_{self.b.pk}": "on"}
        data.update(extra)
        return self.client.post(reverse("add_expense", args=[self.group.pk]), data)

    def test_expense_updates_balances(self):
        self.assertEqual(self.post_expense().status_code, 302)
        net = net_balances(self.group)
        self.assertEqual((net[self.a.pk], net[self.b.pk]), (15000, -15000))

    def test_settlement_clears_balance(self):
        self.post_expense()
        self.client.post(reverse("settle", args=[self.group.pk]),
                         {"payer": self.b.pk, "payee": self.a.pk, "cents": 15000})
        self.assertTrue(all(v == 0 for v in net_balances(self.group).values()))

    def test_non_members_cannot_view_group(self):
        outsider = User.objects.create_user("cy", password="pw12345!")
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("group_detail", args=[self.group.pk])).status_code, 404)

    def test_bad_percent_split_is_rejected(self):
        resp = self.post_expense(split_type="percent", **{f"val_{self.a.pk}": "50", f"val_{self.b.pk}": "40"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self.group.expenses.count(), 0)


class GuestTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("ana", password="pw12345!")
        self.group = Group.objects.create(name="Trip", owner=self.a)
        self.group.members.add(self.a)
        self.client.force_login(self.a)
        self.client.post(reverse("add_guest", args=[self.group.pk]), {"name": "Migs"})
        self.guest = self.group.guests.get().user

    def test_guest_is_member_without_login(self):
        self.assertIn(self.guest, self.group.members.all())
        self.assertFalse(self.guest.is_active)
        self.assertFalse(self.guest.has_usable_password())

    def test_blank_guest_name_rejected(self):
        self.client.post(reverse("add_guest", args=[self.group.pk]), {"name": "   "})
        self.assertEqual(self.group.guests.count(), 1)

    def test_guest_can_be_split_with_and_settled(self):
        self.client.post(reverse("add_expense", args=[self.group.pk]), {
            "description": "Lunch", "amount": "200", "paid_by": self.a.pk, "split_type": "equal",
            "date": "2026-10-02", f"inc_{self.a.pk}": "on", f"inc_{self.guest.pk}": "on"})
        self.assertEqual(net_balances(self.group)[self.guest.pk], -10000)
        self.client.post(reverse("settle", args=[self.group.pk]),
                         {"payer": self.guest.pk, "payee": self.a.pk, "cents": 10000})
        self.assertTrue(all(v == 0 for v in net_balances(self.group).values()))
