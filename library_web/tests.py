from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import Book


User = get_user_model()


class LibraryWebTests(TestCase):
    def setUp(self):
        self.librarian = User.objects.create_user(
            username='matheu_admin',
            email='matheu_admin@example.com',
            password='Biblioteca2026!',
            role=User.ROLE_LIBRARIAN,
        )
        self.reader = User.objects.create_user(
            username='matheu_lector',
            email='matheu_lector@example.com',
            password='Biblioteca2026!',
        )

    def test_root_redirects_to_login_when_anonymous(self):
        response = self.client.get('/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('library_web:login'))

    def test_librarian_login_redirects_to_librarian_dashboard(self):
        response = self.client.post(
            reverse('library_web:login'),
            {'username': 'matheu_admin', 'password': 'Biblioteca2026!'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('library_web:librarian_dashboard'))

    def test_reader_login_redirects_to_reader_dashboard(self):
        response = self.client.post(
            reverse('library_web:login'),
            {'username': 'matheu_lector', 'password': 'Biblioteca2026!'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], reverse('library_web:reader_dashboard'))

    def test_librarian_dashboard_has_admin_navigation_and_charts(self):
        self.client.force_login(self.librarian)

        response = self.client.get(reverse('library_web:librarian_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Consola bibliotecaria')
        self.assertContains(response, 'Usuarios')
        self.assertContains(response, 'Prestamos por mes')

    def test_reader_dashboard_does_not_show_admin_navigation(self):
        self.client.force_login(self.reader)

        response = self.client.get(reverse('library_web:reader_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Portal lector')
        self.assertNotContains(response, 'Consola bibliotecaria')
        self.assertNotContains(response, 'Usuarios')

    def test_reader_cannot_access_librarian_area(self):
        self.client.force_login(self.reader)

        response = self.client.get(reverse('library_web:user_list'), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.redirect_chain[-1][0], reverse('library_web:reader_dashboard'))
        self.assertContains(response, 'Portal lector')
        self.assertNotContains(response, 'Nuevo usuario')

    def test_librarian_can_open_book_crud_page(self):
        Book.objects.create(title='Libro web', isbn='web-1', total_copies=1, available_copies=1)
        self.client.force_login(self.librarian)

        response = self.client.get(reverse('library_web:book_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Libro web')
        self.assertContains(response, 'Nuevo libro')

    def test_reader_can_open_catalog_without_admin_actions(self):
        Book.objects.create(title='Libro lector', isbn='reader-1', total_copies=1, available_copies=1)
        self.client.force_login(self.reader)

        response = self.client.get(reverse('library_web:reader_book_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Libro lector')
        self.assertContains(response, 'Reservar')
        self.assertNotContains(response, 'Nuevo libro')
        self.assertNotContains(response, 'Eliminar')

    def test_admin_dashboard_redirects_to_librarian_interface(self):
        response = self.client.get('/admin-dashboard/')

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/bibliotecario/')
