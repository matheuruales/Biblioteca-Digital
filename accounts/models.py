from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models


class UserManager(DjangoUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('role', 'librarian')
        extra_fields.setdefault('status', 'active')
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    ROLE_READER = 'reader'
    ROLE_LIBRARIAN = 'librarian'

    ROLE_CHOICES = (
        (ROLE_READER, 'Lector'),
        (ROLE_LIBRARIAN, 'Bibliotecario'),
    )

    STATUS_ACTIVE = 'active'
    STATUS_BLOCKED = 'blocked'

    STATUS_CHOICES = (
        (STATUS_ACTIVE, 'Activo'),
        (STATUS_BLOCKED, 'Bloqueado'),
    )

    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_READER,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    objects = UserManager()

    REQUIRED_FIELDS = ['email']

    @property
    def is_librarian(self):
        return self.is_superuser or self.role == self.ROLE_LIBRARIAN

    @property
    def is_blocked(self):
        return self.status == self.STATUS_BLOCKED
