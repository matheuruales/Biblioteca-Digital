from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Book

from .models import Loan, Reservation, Sanction

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class CirculationApiTests(APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(
            username='reader',
            email='reader@example.com',
            password='StrongPass123!',
        )
        self.librarian = User.objects.create_user(
            username='lib',
            email='lib@example.com',
            password='StrongPass123!',
            role=User.ROLE_LIBRARIAN,
        )
        self.book = Book.objects.create(
            title='Libro',
            isbn='isbn-1',
            total_copies=2,
            available_copies=2,
        )

    def test_reader_can_reserve_and_cancel_reservation(self):
        self.client.force_authenticate(self.reader)

        reserve_response = self.client.post(
            '/api/reservations/',
            {'book_id': self.book.id},
            format='json',
        )
        self.assertEqual(reserve_response.status_code, status.HTTP_201_CREATED)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)
        self.assertEqual(len(mail.outbox), 1)

        reservation_id = reserve_response.data['id']
        cancel_response = self.client.post(f'/api/reservations/{reservation_id}/cancel/')
        self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

    def test_reader_cannot_reserve_unavailable_book(self):
        self.book.available_copies = 0
        self.book.save(update_fields=['available_copies'])

        self.client.force_authenticate(self.reader)
        response = self.client.post('/api/reservations/', {'book_id': self.book.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_librarian_can_create_loan_using_reservation_without_double_decrement(self):
        self.client.force_authenticate(self.reader)
        reserve_response = self.client.post('/api/reservations/', {'book_id': self.book.id}, format='json')
        self.assertEqual(reserve_response.status_code, status.HTTP_201_CREATED)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

        self.client.force_authenticate(self.librarian)
        loan_response = self.client.post(
            '/api/loans/',
            {'book_id': self.book.id, 'user_id': self.reader.id},
            format='json',
        )
        self.assertEqual(loan_response.status_code, status.HTTP_201_CREATED)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

    def test_return_loan_increments_availability(self):
        self.client.force_authenticate(self.librarian)
        loan_response = self.client.post(
            '/api/loans/',
            {'book_id': self.book.id, 'user_id': self.reader.id},
            format='json',
        )
        self.assertEqual(loan_response.status_code, status.HTTP_201_CREATED)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

        loan_id = loan_response.data['id']
        return_response = self.client.post(f'/api/loans/{loan_id}/return/')
        self.assertEqual(return_response.status_code, status.HTTP_200_OK)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 2)

    def test_overdue_return_creates_sanction_and_blocks_reservations(self):
        past_due = timezone.now() - timedelta(days=2)
        loan = Loan.objects.create(user=self.reader, book=self.book, due_at=past_due, created_by=self.librarian)
        self.book.available_copies = 1
        self.book.save(update_fields=['available_copies'])

        self.client.force_authenticate(self.librarian)
        return_response = self.client.post(f'/api/loans/{loan.id}/return/')
        self.assertEqual(return_response.status_code, status.HTTP_200_OK)

        self.assertTrue(Sanction.objects.filter(user=self.reader, loan=loan).exists())

        self.client.force_authenticate(self.reader)
        reserve_response = self.client.post('/api/reservations/', {'book_id': self.book.id}, format='json')
        self.assertEqual(reserve_response.status_code, status.HTTP_403_FORBIDDEN)

    # La cobertura del comando `circulation_maintenance` se agrega en la rama de mantenimiento (Dev2).
# Create your tests here.
