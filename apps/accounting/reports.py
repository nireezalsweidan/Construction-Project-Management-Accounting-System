"""
Read-only reporting calculations for the ``accounting`` app's Financial
Reports (Core) slice.

These are deliberately separated from ``accounting.services`` (which owns
the write side: posting/voiding journal entries) so the reports layer can
grow without touching the balance/status business logic. All functions here
are pure reads over POSTED transactions -- DRAFT is never counted (nothing
is booked yet) and VOIDED is never counted (the entry was reversed by
booking a separate correction, per ``void_transaction``'s docstring).

Debit/credit direction rules (standard double-entry convention):

* A REVENUE account increases on the credit side  -> contribution = credit - debit
* An EXPENSE account increases on the debit side  -> contribution = debit - credit

The ``account_type`` column is free text (not an enum), so the type is
normalized with a small case-insensitive mapping rather than an exact match.
"""
from collections import OrderedDict
from decimal import Decimal

from django.db.models import Q, Sum

from construction.filtering import filter_date_range

from .models import FinancialTransaction, TransactionLine

# account_type is free text (VARCHAR) -- "Revenue"/"Income"/"Sales" all mean
# a revenue account; "Expense"/"Cost"/"Operating Expense" all mean expense.
_REVENUE_TOKENS = ("revenue", "income", "sales")
_EXPENSE_TOKENS = ("expense", "cost", "cost_of")


def _type_bucket(account_type):
    """Return 'revenue', 'expense', or None for a free-text account_type."""
    token = (account_type or "").strip().lower()
    if any(t in token for t in _REVENUE_TOKENS):
        return "revenue"
    if any(t in token for t in _EXPENSE_TOKENS):
        return "expense"
    return None


def _posted_lines(params):
    """Base queryset: lines on POSTED transactions, optionally date/project filtered.

    Line-level project dimension takes precedence (a single entry can span
    lines on different projects), falling back to the header's project.
    """
    queryset = TransactionLine.objects.filter(
        transaction__status=FinancialTransaction.Status.POSTED,
    ).select_related('account', 'transaction', 'transaction__project', 'project')

    queryset = filter_date_range(
        queryset, params, 'transaction__transaction_date',
    )

    project_id = params.get('project')
    if project_id:
        queryset = queryset.filter(
            Q(project_id=project_id) | Q(transaction__project_id=project_id)
        )

    return queryset


def profit_loss(params):
    """
    Build a Profit & Loss summary from posted journal lines.

    ``params`` is a query-param mapping with optional keys ``date_from``,
    ``date_to``, ``project``. Returns revenue and expense totals (global +
    per account) and NET profit for the selected period/project. The per
    account breakdown lets the UI render a statement, not just one number.
    """
    queryset = _posted_lines(params)

    # Debit/credit balance grouped by account so the sign logic below is
    # applied per account, then summed.
    by_account = (
        queryset
        .values('account_id', 'account__code', 'account__name', 'account__account_type')
        .annotate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit'),
        )
        .order_by('account__code')
    )

    revenue_accounts = []
    expense_accounts = []
    total_revenue = Decimal('0.00')
    total_expense = Decimal('0.00')

    for row in by_account:
        bucket = _type_bucket(row['account__account_type'])
        if bucket is None:
            continue
        debit = row['total_debit'] or Decimal('0.00')
        credit = row['total_credit'] or Decimal('0.00')
        if bucket == 'revenue':
            amount = credit - debit
            total_revenue += amount
            revenue_accounts.append(_account_row(row, amount))
        else:
            amount = debit - credit
            total_expense += amount
            expense_accounts.append(_account_row(row, amount))

    net_profit = total_revenue - total_expense

    return {
        'date_from': params.get('date_from') or None,
        'date_to': params.get('date_to') or None,
        'project': params.get('project') or None,
        'revenue': {
            'total': str(total_revenue),
            'accounts': revenue_accounts,
        },
        'expenses': {
            'total': str(total_expense),
            'accounts': expense_accounts,
        },
        'net_profit': str(net_profit),
    }


def _account_row(group_row, amount):
    return {
        'account_id': str(group_row['account_id']),
        'code': group_row['account__code'],
        'name': group_row['account__name'],
        'account_type': group_row['account__account_type'],
        'amount': str(amount),
    }


def revenue_expense_trend(params):
    """
    Monthly revenue-vs-expense series from posted journal lines, for the
    Revenue & expense trend chart. ``params`` is a query-param mapping with
    optional ``date_from``/``date_to``/``project``. Returns one entry per
    month present in the data, each with revenue and expense totals.
    """
    from django.db.models.functions import TruncMonth

    queryset = _posted_lines(params)

    by_month = (
        queryset
        .annotate(month=TruncMonth('transaction__transaction_date'))
        .values('month', 'account__account_type')
        .annotate(total_debit=Sum('debit'), total_credit=Sum('credit'))
        .order_by('month')
    )

    series = OrderedDict()  # month -> {revenue, expense, debit, credit}
    for row in by_month:
        bucket = _type_bucket(row['account__account_type'])
        if bucket is None or row['month'] is None:
            continue
        month_key = row['month'].strftime('%Y-%m')
        entry = series.setdefault(month_key, {
            'month': month_key,
            'revenue': Decimal('0.00'),
            'expense': Decimal('0.00'),
        })
        debit = row['total_debit'] or Decimal('0.00')
        credit = row['total_credit'] or Decimal('0.00')
        if bucket == 'revenue':
            entry['revenue'] += credit - debit
        else:
            entry['expense'] += debit - credit

    result = []
    for entry in series.values():
        result.append({
            'month': entry['month'],
            'revenue': str(entry['revenue']),
            'expense': str(entry['expense']),
        })
    return result
