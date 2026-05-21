from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from catalog.models import Book

from .models import Loan, Reservation, Sanction
from .services import (
    calculate_overdue_days,
    default_reservation_expires_at,
    user_has_active_sanction,
)


User = get_user_model()


class BookBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ('id', 'title', 'isbn')
        read_only_fields = fields


class ReservationSerializer(serializers.ModelSerializer):
    book = BookBriefSerializer(read_only=True)

    class Meta:
        model = Reservation
        fields = (
            'id',
            'book',
            'status',
            'reserved_at',
            'expires_at',
            'canceled_at',
            'fulfilled_at',
        )
        read_only_fields = fields


class ReservationCreateSerializer(serializers.Serializer):
    book_id = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all(), source='book')

    def validate(self, attrs):
        user = self.context['request'].user
        book = attrs['book']
        now = timezone.now()

        if user_has_active_sanction(user):
            raise serializers.ValidationError('Usuario con sanción activa. No puede reservar.')

        if not book.is_available:
            raise serializers.ValidationError('No hay copias disponibles para reservar.')

        if Loan.objects.filter(
            user=user,
            book=book,
            status__in=(Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE),
        ).exists():
            raise serializers.ValidationError('Ya tienes un préstamo activo de este libro.')

        if Reservation.objects.filter(
            user=user,
            book=book,
            status=Reservation.STATUS_ACTIVE,
            expires_at__gt=now,
        ).exists():
            raise serializers.ValidationError('Ya tienes una reserva activa de este libro.')

        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        book = validated_data['book']

        reservation_hours = getattr(settings, 'CIRCULATION_RESERVATION_HOURS', 48)
        expires_at = default_reservation_expires_at(reservation_hours=reservation_hours)

        return Reservation.objects.create(
            user=user,
            book=book,
            status=Reservation.STATUS_ACTIVE,
            expires_at=expires_at,
        )


class ReservationCancelSerializer(serializers.Serializer):
    def validate(self, attrs):
        reservation = self.context['reservation']
        if reservation.status != Reservation.STATUS_ACTIVE:
            raise serializers.ValidationError('Solo se puede cancelar una reserva activa.')
        if reservation.expires_at and reservation.expires_at <= timezone.now():
            raise serializers.ValidationError('La reserva ya expiró.')
        return attrs


class LoanSerializer(serializers.ModelSerializer):
    book = BookBriefSerializer(read_only=True)
    overdue_days = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = (
            'id',
            'book',
            'status',
            'loaned_at',
            'due_at',
            'returned_at',
            'overdue_days',
            'user_id',
        )
        read_only_fields = fields

    def get_overdue_days(self, obj):
        if obj.status in (Loan.STATUS_RETURNED, Loan.STATUS_RETURNED_LATE):
            return calculate_overdue_days(obj, at_time=obj.returned_at)
        return calculate_overdue_days(obj)


class LoanCreateSerializer(serializers.Serializer):
    book_id = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all(), source='book')
    user_id = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), source='user')
    due_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        user = attrs['user']
        book = attrs['book']
        now = timezone.now()

        if user_has_active_sanction(user):
            raise serializers.ValidationError('Usuario con sanción activa. No puede prestar.')

        open_loans_count = Loan.objects.filter(
            user=user,
            status__in=(Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE),
        ).count()
        max_loans = getattr(settings, 'CIRCULATION_MAX_ACTIVE_LOANS', 3)
        if open_loans_count >= max_loans:
            raise serializers.ValidationError(f'Límite de préstamos alcanzado ({max_loans}).')

        if Loan.objects.filter(
            user=user,
            book=book,
            status__in=(Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE),
        ).exists():
            raise serializers.ValidationError('El usuario ya tiene un préstamo abierto de este libro.')

        if not Reservation.objects.filter(
            user=user,
            book=book,
            status=Reservation.STATUS_ACTIVE,
            expires_at__gt=now,
        ).exists() and not book.is_available:
            raise serializers.ValidationError('No hay copias disponibles para prestar.')

        return attrs


class LoanReturnSerializer(serializers.Serializer):
    def validate(self, attrs):
        loan = self.context['loan']
        if loan.status == Loan.STATUS_RETURNED:
            raise serializers.ValidationError('Este préstamo ya fue devuelto.')
        return attrs


class SanctionSerializer(serializers.ModelSerializer):
    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Sanction
        fields = (
            'id',
            'user_id',
            'loan_id',
            'reason',
            'amount',
            'created_at',
            'ends_at',
            'cleared_at',
            'is_active',
        )
        read_only_fields = fields
