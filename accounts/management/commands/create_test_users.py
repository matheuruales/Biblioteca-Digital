from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Crea credenciales de prueba para la biblioteca.'

    def handle(self, *args, **options):
        User = get_user_model()
        specs = (
            ('matheu_admin', 'matheu_admin@example.com', User.ROLE_LIBRARIAN, True),
            ('matheu_lector', 'matheu_lector@example.com', User.ROLE_READER, False),
        )
        for username, email, role, is_staff in specs:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'role': role, 'status': User.STATUS_ACTIVE},
            )
            user.email = email
            user.role = role
            user.status = User.STATUS_ACTIVE
            user.is_staff = is_staff
            user.set_password('Biblioteca2026!')
            user.save()
        self.stdout.write(self.style.SUCCESS('Credenciales listas: matheu_admin y matheu_lector'))
