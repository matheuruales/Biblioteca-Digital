from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from catalog.models import Author, Book, Category
from circulation.models import Loan, Reservation
from circulation.services import upsert_sanction_for_loan


class Command(BaseCommand):
    help = 'Crea datos de demostracion para dashboard, CRUD, prestamos y reportes.'

    def handle(self, *args, **options):
        call_command('create_test_users')
        User = get_user_model()
        librarian = User.objects.get(username='matheu_admin')
        reader = User.objects.get(username='matheu_lector')

        with transaction.atomic():
            novel = Category.objects.get_or_create(name='Novela')[0]
            technology = Category.objects.get_or_create(name='Tecnologia')[0]
            history = Category.objects.get_or_create(name='Historia')[0]

            garcia = Author.objects.get_or_create(name='Gabriel Garcia Marquez')[0]
            allende = Author.objects.get_or_create(name='Isabel Allende')[0]
            turing = Author.objects.get_or_create(name='Alan Turing')[0]

            one_hundred = self._book(
                'Cien anos de soledad',
                'demo-001',
                4,
                [garcia],
                [novel],
            )
            spirits = self._book(
                'La casa de los espiritus',
                'demo-002',
                3,
                [allende],
                [novel, history],
            )
            computing = self._book(
                'Computacion y pensamiento',
                'demo-003',
                2,
                [turing],
                [technology],
            )

            reservation, created = Reservation.objects.get_or_create(
                user=reader,
                book=one_hundred,
                status=Reservation.STATUS_ACTIVE,
                defaults={'expires_at': timezone.now() + timedelta(hours=24)},
            )
            if created and one_hundred.available_copies > 0:
                one_hundred.available_copies -= 1
                one_hundred.save(update_fields=['available_copies'])

            self._loan(reader, spirits, librarian, timezone.now() + timedelta(days=7))
            overdue = self._loan(reader, computing, librarian, timezone.now() - timedelta(days=2))
            if overdue.status != Loan.STATUS_OVERDUE:
                overdue.status = Loan.STATUS_OVERDUE
                overdue.save(update_fields=['status'])
            upsert_sanction_for_loan(overdue)

        self.stdout.write(self.style.SUCCESS('Datos demo listos.'))

    def _book(self, title, isbn, total_copies, authors, categories):
        book, _ = Book.objects.get_or_create(
            isbn=isbn,
            defaults={
                'title': title,
                'total_copies': total_copies,
                'available_copies': total_copies,
            },
        )
        book.title = title
        book.total_copies = total_copies
        book.available_copies = min(book.available_copies, total_copies)
        book.save()
        book.authors.set(authors)
        book.categories.set(categories)
        return book

    def _loan(self, user, book, librarian, due_at):
        loan = Loan.objects.filter(
            user=user,
            book=book,
            status__in=(Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE),
        ).first()
        if loan:
            return loan
        loan = Loan.objects.create(
            user=user,
            book=book,
            created_by=librarian,
            due_at=due_at,
            status=Loan.STATUS_OVERDUE if due_at < timezone.now() else Loan.STATUS_ACTIVE,
        )
        if book.available_copies > 0:
            book.available_copies -= 1
            book.save(update_fields=['available_copies'])
        return loan
