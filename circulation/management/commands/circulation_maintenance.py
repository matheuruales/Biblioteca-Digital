from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from circulation.models import Loan
from circulation.services import (
    clear_expired_sanctions,
    due_soon_queryset,
    expire_reservations,
    mark_overdue_loans,
    overdue_queryset,
    send_due_soon_email,
    send_overdue_email,
    upsert_sanction_for_loan,
)


class Command(BaseCommand):
    help = 'Ejecuta tareas de circulación: expiración de reservas, vencimientos, sanciones y correos.'

    def handle(self, *args, **options):
        now = timezone.now()

        with transaction.atomic():
            expired_reservations = expire_reservations(at_time=now)
            marked_overdue = mark_overdue_loans(at_time=now)

            due_soon_loans = list(
                due_soon_queryset(at_time=now).select_for_update().select_related('book', 'user')
            )
            for loan in due_soon_loans:
                send_due_soon_email(loan)
                loan.due_soon_notified_at = now
                loan.save(update_fields=['due_soon_notified_at'])

            overdue_loans = list(
                overdue_queryset(at_time=now).select_for_update().select_related('book', 'user')
            )
            for loan in overdue_loans:
                upsert_sanction_for_loan(loan, at_time=now)
                send_overdue_email(loan)
                loan.overdue_notified_at = now
                loan.status = Loan.STATUS_OVERDUE
                loan.save(update_fields=['overdue_notified_at', 'status'])

            cleared_sanctions = clear_expired_sanctions(at_time=now)

        self.stdout.write(
            self.style.SUCCESS(
                'OK - '
                f'expired_reservations={expired_reservations}, '
                f'marked_overdue_loans={marked_overdue}, '
                f'due_soon_emails={len(due_soon_loans)}, '
                f'overdue_emails={len(overdue_loans)}, '
                f'cleared_sanctions={cleared_sanctions}'
            )
        )

