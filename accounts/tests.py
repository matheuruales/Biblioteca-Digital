from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()


class AuthApiTests(APITestCase):
    def test_register_creates_reader(self):
        response = self.client.post(
            '/api/auth/register/',
            {
                'username': 'ana',
                'email': 'ana@example.com',
                'password': 'StrongPass123!',
                'role': User.ROLE_LIBRARIAN,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='ana')
        self.assertEqual(user.role, User.ROLE_READER)
        self.assertEqual(user.status, User.STATUS_ACTIVE)
        self.assertNotIn('password', response.data)

    def test_jwt_login_and_refresh(self):
        User.objects.create_user(
            username='reader',
            email='reader@example.com',
            password='StrongPass123!',
        )

        response = self.client.post(
            '/api/auth/token/',
            {'username': 'reader', 'password': 'StrongPass123!'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

        refresh_response = self.client.post(
            '/api/auth/token/refresh/',
            {'refresh': response.data['refresh']},
            format='json',
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', refresh_response.data)

    def test_blocked_user_cannot_login(self):
        User.objects.create_user(
            username='blocked',
            email='blocked@example.com',
            password='StrongPass123!',
            status=User.STATUS_BLOCKED,
        )

        response = self.client.post(
            '/api/auth/token/',
            {'username': 'blocked', 'password': 'StrongPass123!'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reader_cannot_manage_users(self):
        reader = User.objects.create_user(
            username='reader',
            email='reader@example.com',
            password='StrongPass123!',
        )
        self.client.force_authenticate(reader)

        response = self.client.post(
            '/api/users/',
            {
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'StrongPass123!',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_manage_users(self):
        librarian = User.objects.create_user(
            username='lib',
            email='lib@example.com',
            password='StrongPass123!',
            role=User.ROLE_LIBRARIAN,
        )
        self.client.force_authenticate(librarian)

        response = self.client.post(
            '/api/users/',
            {
                'username': 'worker',
                'email': 'worker@example.com',
                'password': 'StrongPass123!',
                'role': User.ROLE_LIBRARIAN,
                'status': User.STATUS_ACTIVE,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(username='worker').role, User.ROLE_LIBRARIAN)

    def test_authenticated_user_can_read_me(self):
        reader = User.objects.create_user(
            username='reader',
            email='reader@example.com',
            password='StrongPass123!',
        )
        self.client.force_authenticate(reader)

        response = self.client.get('/api/users/me/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'reader')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset_request_sends_email_and_confirm_changes_password(self):
        user = User.objects.create_user(
            username='reset',
            email='reset@example.com',
            password='StrongPass123!',
        )

        response = self.client.post(
            '/api/auth/password-reset/',
            {'email': 'reset@example.com'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(mail.outbox), 1)

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        confirm_response = self.client.post(
            '/api/auth/password-reset-confirm/',
            {
                'uid': uid,
                'token': token,
                'new_password': 'NewStrongPass123!',
            },
            format='json',
        )

        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
        login_response = self.client.post(
            '/api/auth/token/',
            {'username': 'reset', 'password': 'NewStrongPass123!'},
            format='json',
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
