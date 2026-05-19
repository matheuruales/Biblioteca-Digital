from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsLibrarian
from catalog.models import Book

from .models import Loan, Reservation, Sanction
from .permissions import IsActiveAuthenticated, IsActiveNonSanctioned
from .serializers import (
    LoanCreateSerializer,
    LoanReturnSerializer,
    LoanSerializer,
    ReservationCancelSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    SanctionSerializer,
)
from .services import (
    calculate_overdue_days,
    clear_expired_sanctions,
    expire_reservations,
    mark_overdue_loans,
    send_loan_email,
    send_reservation_email,
    upsert_sanction_for_loan,
    user_has_active_sanction,
)


User = get_user_model()


class ReservationViewSet(viewsets.GenericViewSet):
    queryset = Reservation.objects.select_related('book', 'user')
    serializer_class = ReservationSerializer
    permission_classes = (IsAuthenticated,)
    http_method_names = ('get', 'post', 'head', 'options')

    def get_permissions(self):
        if self.action in ('create',):
            return [IsActiveNonSanctioned()]
        return [IsActiveAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'is_librarian', False):
            return qs
        return qs.filter(user=user)

    def list(self, request):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = ReservationCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                book = Book.objects.select_for_update().get(pk=serializer.validated_data['book'].pk)
                if book.available_copies <= 0:
                    return Response(
                        {'detail': 'No hay copias disponibles para reservar.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                reservation = serializer.create({'book': book})
                book.available_copies = book.available_copies - 1
                book.save(update_fields=['available_copies'])
        except IntegrityError:
            return Response(
                {'detail': 'Ya existe una reserva activa para este libro.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_reservation_email(reservation)
        return Response(ReservationSerializer(reservation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=('post',), url_path='cancel')
    def cancel(self, request, pk=None):
        reservation = get_object_or_404(self.get_queryset(), pk=pk)
        serializer = ReservationCancelSerializer(data=request.data, context={'reservation': reservation})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            reservation = Reservation.objects.select_for_update().select_related('book').get(pk=reservation.pk)
            if reservation.status != Reservation.STATUS_ACTIVE:
                return Response(
                    {'detail': 'Solo se puede cancelar una reserva activa.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            reservation.status = Reservation.STATUS_CANCELED
            reservation.canceled_at = timezone.now()
            reservation.save(update_fields=['status', 'canceled_at'])
            book = reservation.book
            book.available_copies = book.available_copies + 1
            book.save(update_fields=['available_copies'])

        return Response(ReservationSerializer(reservation).data, status=status.HTTP_200_OK)


class LoanViewSet(viewsets.GenericViewSet):
    queryset = Loan.objects.select_related('book', 'user', 'created_by')
    serializer_class = LoanSerializer
    permission_classes = (IsAuthenticated,)
    http_method_names = ('get', 'post', 'head', 'options')

    def get_permissions(self):
        if self.action in ('create', 'return_loan'):
            return [IsLibrarian()]
        return [IsActiveAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'is_librarian', False):
            return qs
        return qs.filter(user=user)

    def list(self, request):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    def create(self, request):
        serializer = LoanCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        book = serializer.validated_data['book']
        due_at = serializer.validated_data.get('due_at')

        if user_has_active_sanction(user):
            return Response(
                {'detail': 'Usuario con sanción activa. No puede prestar.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                book = Book.objects.select_for_update().get(pk=book.pk)

                reservation = Reservation.objects.select_for_update().filter(
                    user=user,
                    book=book,
                    status=Reservation.STATUS_ACTIVE,
                    expires_at__gt=timezone.now(),
                ).order_by('-reserved_at').first()

                if reservation:
                    reservation.status = Reservation.STATUS_FULFILLED
                    reservation.fulfilled_at = timezone.now()
                    reservation.save(update_fields=['status', 'fulfilled_at'])
                else:
                    if book.available_copies <= 0:
                        return Response(
                            {'detail': 'No hay copias disponibles para prestar.'},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    book.available_copies = book.available_copies - 1
                    book.save(update_fields=['available_copies'])

                loan = Loan.objects.create(
                    user=user,
                    book=book,
                    created_by=request.user,
                    due_at=due_at or Loan._meta.get_field('due_at').get_default(),
                )
        except IntegrityError:
            return Response(
                {'detail': 'Ya existe un préstamo abierto para este usuario y libro.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        send_loan_email(loan)
        return Response(LoanSerializer(loan).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=('post',), url_path='return')
    def return_loan(self, request, pk=None):
        loan = get_object_or_404(self.queryset, pk=pk)
        serializer = LoanReturnSerializer(data=request.data, context={'loan': loan})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            loan = Loan.objects.select_for_update().select_related('book', 'user').get(pk=loan.pk)
            if loan.status == Loan.STATUS_RETURNED:
                return Response({'detail': 'Este préstamo ya fue devuelto.'}, status=400)

            now = timezone.now()
            loan.returned_at = now
            overdue_days = calculate_overdue_days(loan, at_time=now)
            if overdue_days > 0:
                loan.status = Loan.STATUS_RETURNED_LATE
                upsert_sanction_for_loan(loan, at_time=now)
            else:
                loan.status = Loan.STATUS_RETURNED

            loan.save(update_fields=['status', 'returned_at'])

            book = loan.book
            book.available_copies = book.available_copies + 1
            book.save(update_fields=['available_copies'])

        return Response(LoanSerializer(loan).data, status=status.HTTP_200_OK)


class SanctionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Sanction.objects.select_related('loan', 'user')
    serializer_class = SanctionSerializer
    permission_classes = (IsActiveAuthenticated,)
    http_method_names = ('get', 'head', 'options')

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if getattr(user, 'is_librarian', False):
            return qs
        return qs.filter(user=user)

    @action(detail=False, methods=('post',), url_path='maintenance', permission_classes=(IsLibrarian,))
    def maintenance(self, request):
        """
        Endpoint opcional para ejecutar mantenimiento manual:
        - Expira reservas vencidas
        - Marca préstamos vencidos como retrasados
        - Crea/actualiza sanciones por retraso
        - Limpia sanciones expiradas
        """
        with transaction.atomic():
            expired_reservations = expire_reservations()
            marked_overdue = mark_overdue_loans()
            overdue_loans = list(SanctionViewSet._overdue_loans_for_sanctions())
            created_sanctions = 0
            for loan in overdue_loans:
                if upsert_sanction_for_loan(loan):
                    created_sanctions += 1
            cleared = clear_expired_sanctions()

        return Response(
            {
                'expired_reservations': expired_reservations,
                'marked_overdue_loans': marked_overdue,
                'processed_overdue_loans': len(overdue_loans),
                'upserted_sanctions': created_sanctions,
                'cleared_sanctions': cleared,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _overdue_loans_for_sanctions():
        now = timezone.now()
        return Loan.objects.filter(
            status__in=(Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE),
            due_at__lt=now,
            returned_at__isnull=True,
        ).select_related('user', 'book')


class BookStateView(APIView):
    permission_classes = (IsActiveAuthenticated,)

    def get(self, request, book_id: int):
        book = get_object_or_404(Book, pk=book_id)
        now = timezone.now()

        active_reservations = Reservation.objects.filter(
            book=book,
            status=Reservation.STATUS_ACTIVE,
        ).count()

        open_loans = Loan.objects.filter(
            book=book,
            status__in=(Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE),
        )
        overdue_loans = open_loans.filter(due_at__lt=now).count()
        open_loans_count = open_loans.count()

        if overdue_loans > 0:
            state = 'retrasado'
        elif open_loans_count > 0:
            state = 'prestado'
        elif active_reservations > 0:
            state = 'reservado'
        else:
            state = 'disponible' if book.available_copies > 0 else 'prestado'

        return Response(
            {
                'book_id': book.id,
                'state': state,
                'total_copies': book.total_copies,
                'available_copies': book.available_copies,
                'active_reservations': active_reservations,
                'open_loans': open_loans_count,
                'overdue_loans': overdue_loans,
            },
            status=status.HTTP_200_OK,
        )

# Create your views here.
