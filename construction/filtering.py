"""
Shared query-param filtering helpers (CPMAS-23: Search, Filtering &
Sorting).

Lives at the project level (not inside a domain app) since it's a
generic cross-cutting utility several apps' viewsets need, the same
reasoning as ``construction/test_runner.py``.

``filter_date_range`` factors out a pattern that already existed,
duplicated, in a few viewsets (e.g. expenses.views.ExpenseViewSet,
inventory.views.StockMovementViewSet) before this ticket: read
``?date_from=``/``?date_to=`` and filter a DateField between them,
silently ignoring an unparseable value rather than raising -- an
invalid query param shouldn't 500 an otherwise-valid list request.
"""
from django.utils.dateparse import parse_date


def filter_date_range(queryset, params, field, date_from_param='date_from', date_to_param='date_to'):
    """
    Filter ``queryset`` on ``field`` (a DateField) using ``date_from``/
    ``date_to`` query params, inclusive on both ends. Either or both may
    be omitted; an unparseable value is treated the same as omitted.
    """
    date_from = parse_date(params.get(date_from_param) or '')
    if date_from:
        queryset = queryset.filter(**{f'{field}__gte': date_from})

    date_to = parse_date(params.get(date_to_param) or '')
    if date_to:
        queryset = queryset.filter(**{f'{field}__lte': date_to})

    return queryset
