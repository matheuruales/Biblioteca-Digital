from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from catalog.models import Author, Book
from circulation.models import Loan, Reservation


User = get_user_model()


class ReportsApiTests(APITestCase):
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
        self.author = Author.objects.create(name='Autora Central')
        self.book = Book.objects.create(
            title='Libro Reportado',
            isbn='report-1',
            total_copies=3,
            available_copies=2,
        )
        self.book.authors.add(self.author)
        Reservation.objects.create(
            user=self.reader,
            book=self.book,
            status=Reservation.STATUS_ACTIVE,
            expires_at=timezone.now() + timedelta(hours=12),
        )
        Loan.objects.create(user=self.reader, book=self.book, created_by=self.librarian)

    def test_reader_cannot_access_dashboard_summary(self):
        self.client.force_authenticate(self.reader)

        response = self.client.get('/api/dashboard/')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_read_dashboard_summary(self):
        self.client.force_authenticate(self.librarian)

        response = self.client.get('/api/dashboard/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['totals']['books'], 1)
        self.assertEqual(response.data['totals']['active_loans'], 1)
        self.assertEqual(response.data['alerts']['expiring_reservations'], 1)

    def test_reports_include_dev3_required_metrics(self):
        self.client.force_authenticate(self.librarian)

        response = self.client.get('/api/reports/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['most_reserved_books'][0]['title'], 'Libro Reportado')
        self.assertEqual(response.data['most_read_authors'][0]['name'], 'Autora Central')
        self.assertEqual(response.data['top_users_by_loans'][0]['username'], 'reader')
        self.assertEqual(response.data['loans_by_month'][0]['total'], 1)

    def test_exports_csv_and_pdf(self):
        self.client.force_authenticate(self.librarian)

        csv_response = self.client.get('/api/reports/export/csv/?report=most_reserved_books')
        pdf_response = self.client.get('/api/reports/export/pdf/?report=loans_by_month')

        self.assertEqual(csv_response.status_code, status.HTTP_200_OK)
        self.assertEqual(csv_response['Content-Type'], 'text/csv')
        self.assertIn(b'Libro Reportado', csv_response.content)
        self.assertEqual(pdf_response.status_code, status.HTTP_200_OK)
        self.assertEqual(pdf_response['Content-Type'], 'application/pdf')
        self.assertTrue(pdf_response.content.startswith(b'%PDF'))

    def test_admin_dashboard_page_renders(self):
        response = self.client.get('/admin-dashboard/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, 'Dashboard administrativo')
        self.assertContains(response, 'admin_dashboard.js')
