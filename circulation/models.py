from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


def default_due_at():
    loan_days = getattr(settings, 'CIRCULATION_LOAN_DAYS', 14)
    return timezone.now() + timedelta(days=loan_days)


class Reservation(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_CANCELED = 'canceled'
    STATUS_FULFILLED = 'fulfilled'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Activa'),
        (STATUS_CANCELED, 'Cancelada'),
        (STATUS_FULFILLED, 'Cumplida'),
        (STATUS_EXPIRED, 'Expirada'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reservations',
    )
    book = models.ForeignKey(
        'catalog.Book',
        on_delete=models.CASCADE,
        related_name='reservations',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    reserved_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    fulfilled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-reserved_at',)
        constraints = (
            models.UniqueConstraint(
                fields=('user', 'book'),
                condition=Q(status='active'),
                name='unique_active_reservation_user_book',
            ),
        )

    @property
    def is_active(self):
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True

    def clean(self):
        if self.expires_at and self.reserved_at and self.expires_at <= self.reserved_at:
            raise ValidationError({'expires_at': 'La expiración debe ser posterior a la reserva.'})

    def __str__(self):
        return f'Reserva #{self.pk} - {self.book_id} - {self.user_id}'


class Loan(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_RETURNED = 'returned'
    STATUS_OVERDUE = 'overdue'
    STATUS_RETURNED_LATE = 'returned_late'

    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Activo'),
        (STATUS_RETURNED, 'Devuelto'),
        (STATUS_OVERDUE, 'Retrasado'),
        (STATUS_RETURNED_LATE, 'Devuelto con retraso'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='loans',
    )
    book = models.ForeignKey(
        'catalog.Book',
        on_delete=models.CASCADE,
        related_name='loans',
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    loaned_at = models.DateTimeField(auto_now_add=True)
    due_at = models.DateTimeField(default=default_due_at)
    returned_at = models.DateTimeField(null=True, blank=True)
    due_soon_notified_at = models.DateTimeField(null=True, blank=True)
    overdue_notified_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='loans_created',
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ('-loaned_at',)
        constraints = (
            models.UniqueConstraint(
                fields=('user', 'book'),
                condition=Q(status__in=('active', 'overdue')),
                name='unique_open_loan_user_book',
            ),
        )

    @property
    def is_open(self):
        return self.status in (self.STATUS_ACTIVE, self.STATUS_OVERDUE)

    @property
    def is_overdue(self):
        return self.is_open and timezone.now() > self.due_at

    def clean(self):
        if self.due_at and self.loaned_at and self.due_at <= self.loaned_at:
            raise ValidationError({'due_at': 'La fecha de vencimiento debe ser posterior al préstamo.'})

    def __str__(self):
        return f'Prestamo #{self.pk} - {self.book_id} - {self.user_id}'


class Sanction(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sanctions',
    )
    loan = models.ForeignKey(
        'circulation.Loan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sanctions',
    )
    reason = models.CharField(max_length=255, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    ends_at = models.DateTimeField()
    cleared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ('-created_at',)

    @property
    def is_active(self):
        return self.cleared_at is None and self.ends_at > timezone.now()

    def __str__(self):
        return f'Sancion #{self.pk} - {self.user_id}'

# Create your models here.
