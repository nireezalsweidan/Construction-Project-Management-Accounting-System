"""
Business logic for the ``expenses`` app that must not live in a
serializer or viewset.

Expense.status only ever changes through transition_status, validated
against ALLOWED_TRANSITIONS -- never a raw field assignment -- so a
client can't jump e.g. straight from PENDING to PAID without ever being
APPROVED. Same reasoning as purchasing.services.transition_status
(CPMAS-30) and invoicing.services.transition_status (CPMAS-32).
"""
from django.core.exceptions import ValidationError

from .models import Expense

ALLOWED_TRANSITIONS = {
    Expense.Status.PENDING: {Expense.Status.APPROVED, Expense.Status.REJECTED},
    Expense.Status.APPROVED: {Expense.Status.PAID, Expense.Status.REJECTED},
    Expense.Status.PAID: set(),
    Expense.Status.REJECTED: set(),
}


def transition_status(expense: Expense, new_status: str) -> Expense:
    """Move an Expense to new_status if valid; raises ValidationError otherwise."""
    current = Expense.Status(expense.status)
    target = Expense.Status(new_status)

    if target not in ALLOWED_TRANSITIONS[current]:
        raise ValidationError(
            f"Cannot move an expense from {current.label} to {target.label}."
        )

    expense.status = target
    expense.save(update_fields=['status', 'updated_at'])
    return expense
