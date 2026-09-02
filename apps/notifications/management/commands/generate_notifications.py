"""
Management command: run every BRD 9 alert generator once (CPMAS-22).

Usage: ``python manage.py generate_notifications``

Meant to be invoked periodically (e.g. a daily cron job / scheduled
task) -- this project has no task-queue/scheduler infrastructure, so
wiring up that schedule is a deployment decision, not something this
command does itself. Each generator in notifications.services is
already deduplicating (see its module docstring), so running this
command more often than needed just no-ops on conditions that are
already flagged and still unread.
"""
from django.core.management.base import BaseCommand

from notifications.services import generate_all_notifications


class Command(BaseCommand):
    help = "Generate BRD 9 alert notifications (overdue invoices, payment due, low inventory, PO approvals, budget overruns, deadlines)."

    def handle(self, *args, **options):
        created = generate_all_notifications()
        self.stdout.write(self.style.SUCCESS(f"Created {len(created)} notification(s)."))
