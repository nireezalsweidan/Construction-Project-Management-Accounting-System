"""
DRF viewsets for the ``notifications`` app (CPMAS-22).
"""
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin,
                           mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    list/retrieve/create for notifications -- no generic update/destroy;
    ``is_read`` changes only through mark_read/mark_all_read below.

    Filterable by ?user=, ?is_read=, ?notification_type=.
    """

    queryset = Notification.objects.select_related('user').all()
    serializer_class = NotificationSerializer
    search_fields = ['title', 'message']
    ordering_fields = ['created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        params = self.request.query_params

        user_id = params.get('user')
        if user_id:
            queryset = queryset.filter(user_id=user_id)

        is_read = params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() in ('true', '1'))

        notification_type = params.get('notification_type')
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type.upper())

        return queryset

    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """POST /api/notifications/notifications/{id}/mark_read/"""
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=['is_read'])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        POST /api/notifications/notifications/mark_all_read/?user=<uuid>
        Marks every unread notification in the current (filtered)
        queryset as read -- e.g. ?user=<uuid> to clear one user's inbox.
        """
        updated = self.filter_queryset(self.get_queryset()).filter(is_read=False).update(is_read=True)
        return Response({'marked_read': updated})
