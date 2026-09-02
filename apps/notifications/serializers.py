"""
DRF serializers for the ``notifications`` app (CPMAS-22).
"""
from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Serializer for Notification CRUD.

    ``is_read`` is read-only here: it only ever changes through the
    viewset's mark_read/mark_all_read actions, never a raw PATCH -- same
    read-only-status pattern used for every other state field in this
    codebase (PurchaseOrder.status, Expense.status, etc).
    """

    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'notification_type', 'title', 'message',
            'entity_type', 'entity_id', 'is_read', 'created_at',
        ]
        read_only_fields = ['is_read', 'created_at']
