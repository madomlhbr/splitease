from django import template

register = template.Library()


@register.filter
def peso(cents):
    cents = int(cents or 0)
    return f"{'-' if cents < 0 else ''}₱{abs(cents) / 100:,.2f}"


@register.filter
def display(user):
    from bills.services import display_name
    return display_name(user)


@register.filter
def is_guest(user):
    from bills.services import is_guest as check
    return check(user)


@register.filter
def initial(user):
    from bills.services import display_name
    return display_name(user)[:1].upper()
