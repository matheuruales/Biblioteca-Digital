from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

from .models import Loan, Reservation, Sanction


def default_reservation_expires_at(*, reservation_hours: int | None = None):
    hours = reservation_hours if reservation_hours is not None else getattr(
        settings, 'CIRCULATION_RESERVATION_HOURS', 48
    )
    return timezone.now() + timedelta(hours=hours)


def user_has_active_sanction(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    now = timezone.now()
    return Sanction.objects.filter(
        user=user,
        cleared_at__isnull=True,
        ends_at__gt=now,
    ).exists()


def calculate_overdue_days(loan: Loan, *, at_time=None) -> int:
    if not loan.due_at:
        return 0
    now = at_time or timezone.now()
    if now <= loan.due_at:
        return 0

    delta = now - loan.due_at
    overdue_days = delta.days
    if delta.seconds or delta.microseconds:
        overdue_days += 1
    return max(0, overdue_days)


def compute_sanction_days(overdue_days: int) -> int:
    multiplier = getattr(settings, 'CIRCULATION_SANCTION_DAYS_PER_OVERDUE_DAY', 1)
    max_days = getattr(settings, 'CIRCULATION_MAX_SANCTION_DAYS', 30)
    if overdue_days <= 0:
        return 0
    days = max(1, overdue_days * multiplier)
    return min(days, max_days)


def upsert_sanction_for_loan(loan: Loan, *, at_time=None) -> Sanction | None:
    now = at_time or timezone.now()
    overdue_days = calculate_overdue_days(loan, at_time=now)
    sanction_days = compute_sanction_days(overdue_days)
    if sanction_days <= 0:
        return None

    ends_at = now + timedelta(days=sanction_days)
    sanction, created = Sanction.objects.get_or_create(
        loan=loan,
        user=loan.user,
        defaults={
            'ends_at': ends_at,
            'reason': 'Retraso en devolución.',
        },
    )
    if not created and (sanction.cleared_at is None) and sanction.ends_at < ends_at:
        sanction.ends_at = ends_at
        sanction.save(update_fields=['ends_at'])
    return sanction


def expire_reservations(*, at_time=None) -> int:
    now = at_time or timezone.now()
    qs = Reservation.objects.select_related('book').filter(
        status=Reservation.STATUS_ACTIVE,
        expires_at__isnull=False,
        expires_at__lte=now,
    )
    count = 0
    for reservation in qs:
        book = reservation.book
        reservation.status = Reservation.STATUS_EXPIRED
        reservation.save(update_fields=['status'])
        book.available_copies = book.available_copies + 1
        book.save(update_fields=['available_copies'])
        count += 1
    return count


def mark_overdue_loans(*, at_time=None) -> int:
    now = at_time or timezone.now()
    qs = Loan.objects.filter(status=Loan.STATUS_ACTIVE, due_at__lt=now)
    return qs.update(status=Loan.STATUS_OVERDUE)


def send_reservation_email(reservation: Reservation):
    send_mail(
        subject='Confirmación de reserva',
        message=(
            f'Tu reserva del libro "{reservation.book.title}" fue registrada.\n'
            f'Expira: {reservation.expires_at}.\n'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[reservation.user.email],
        fail_silently=False,
    )


def send_loan_email(loan: Loan):
    send_mail(
        subject='Confirmación de préstamo',
        message=(
            f'Tu préstamo del libro "{loan.book.title}" fue registrado.\n'
            f'Vence: {loan.due_at}.\n'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[loan.user.email],
        fail_silently=False,
    )


def send_due_soon_email(loan: Loan):
    send_mail(
        subject='Aviso de vencimiento',
        message=(
            f'Tu préstamo del libro "{loan.book.title}" vence pronto.\n'
            f'Vence: {loan.due_at}.\n'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[loan.user.email],
        fail_silently=False,
    )


def send_overdue_email(loan: Loan):
    overdue_days = calculate_overdue_days(loan)
    send_mail(
        subject='Aviso de retraso',
        message=(
            f'Tu préstamo del libro "{loan.book.title}" está retrasado.\n'
            f'Venció: {loan.due_at}.\n'
            f'Días de retraso (aprox): {overdue_days}.\n'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[loan.user.email],
        fail_silently=False,
    )


def due_soon_queryset(*, at_time=None):
    now = at_time or timezone.now()
    hours = getattr(settings, 'CIRCULATION_DUE_SOON_HOURS', 24)
    upper = now + timedelta(hours=hours)
    return Loan.objects.filter(
        status__in=(Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE),
        due_at__gte=now,
        due_at__lte=upper,
        due_soon_notified_at__isnull=True,
    ).select_related('book', 'user')


def overdue_queryset(*, at_time=None):
    now = at_time or timezone.now()
    return Loan.objects.filter(
        status__in=(Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE),
        due_at__lt=now,
        returned_at__isnull=True,
        overdue_notified_at__isnull=True,
    ).select_related('book', 'user')


def open_loans_queryset_for_user(user):
    return Loan.objects.filter(
        user=user,
        status__in=(Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE),
    )


def clear_expired_sanctions(*, at_time=None) -> int:
    now = at_time or timezone.now()
    qs = Sanction.objects.filter(cleared_at__isnull=True, ends_at__lte=now)
    return qs.update(cleared_at=now)


def user_is_allowed_to_borrow(user) -> tuple[bool, str | None]:
    if user_has_active_sanction(user):
        return False, 'Usuario con sanción activa.'
    return True, None
