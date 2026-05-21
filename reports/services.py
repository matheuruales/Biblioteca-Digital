import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from catalog.models import Author, Book
from circulation.models import Loan, Reservation, Sanction


User = get_user_model()


REPORT_LABELS = {
    'most_reserved_books': 'Libros mas reservados',
    'most_read_authors': 'Autores mas leidos',
    'loans_by_month': 'Prestamos por mes',
    'top_users_by_loans': 'Usuarios con mas prestamos',
}


def _month_label(value):
    return value.strftime('%Y-%m') if value else 'Sin fecha'


def dashboard_summary():
    now = timezone.now()
    open_statuses = (Loan.STATUS_ACTIVE, Loan.STATUS_OVERDUE)

    return {
        'generated_at': now,
        'totals': {
            'books': Book.objects.count(),
            'users': User.objects.count(),
            'readers': User.objects.filter(role=User.ROLE_READER).count(),
            'librarians': User.objects.filter(role=User.ROLE_LIBRARIAN).count(),
            'loans': Loan.objects.count(),
            'active_loans': Loan.objects.filter(status__in=open_statuses).count(),
            'reservations': Reservation.objects.count(),
            'active_reservations': Reservation.objects.filter(
                status=Reservation.STATUS_ACTIVE,
                expires_at__gt=now,
            ).count(),
            'active_sanctions': Sanction.objects.filter(
                cleared_at__isnull=True,
                ends_at__gt=now,
            ).count(),
        },
        'book_inventory': {
            'total_copies': sum(Book.objects.values_list('total_copies', flat=True)),
            'available_copies': sum(Book.objects.values_list('available_copies', flat=True)),
            'unavailable_books': Book.objects.filter(available_copies=0).count(),
        },
        'loan_statuses': list(
            Loan.objects.values('status')
            .annotate(total=Count('id'))
            .order_by('status')
        ),
        'reservation_statuses': list(
            Reservation.objects.values('status')
            .annotate(total=Count('id'))
            .order_by('status')
        ),
        'alerts': {
            'overdue_loans': Loan.objects.filter(
                status__in=open_statuses,
                due_at__lt=now,
                returned_at__isnull=True,
            ).count(),
            'expiring_reservations': Reservation.objects.filter(
                status=Reservation.STATUS_ACTIVE,
                expires_at__gt=now,
                expires_at__lte=now + timezone.timedelta(hours=24),
            ).count(),
            'blocked_users': User.objects.filter(status=User.STATUS_BLOCKED).count(),
        },
    }


def most_reserved_books(limit=10):
    return list(
        Book.objects.annotate(reservations_count=Count('reservations'))
        .filter(reservations_count__gt=0)
        .order_by('-reservations_count', 'title')
        .values('id', 'title', 'isbn', 'reservations_count')[:limit]
    )


def most_read_authors(limit=10):
    return list(
        Author.objects.annotate(
            loans_count=Count('books__loans', filter=Q(books__loans__isnull=False))
        )
        .filter(loans_count__gt=0)
        .order_by('-loans_count', 'name')
        .values('id', 'name', 'loans_count')[:limit]
    )


def loans_by_month(limit=12):
    rows = (
        Loan.objects.annotate(month=TruncMonth('loaned_at'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('-month')[:limit]
    )
    return [
        {
            'month': _month_label(row['month']),
            'total': row['total'],
        }
        for row in reversed(list(rows))
    ]


def top_users_by_loans(limit=10):
    return list(
        User.objects.annotate(loans_count=Count('loans'))
        .filter(loans_count__gt=0)
        .order_by('-loans_count', 'username')
        .values('id', 'username', 'email', 'loans_count')[:limit]
    )


def all_reports(limit=10):
    return {
        'most_reserved_books': most_reserved_books(limit),
        'most_read_authors': most_read_authors(limit),
        'loans_by_month': loans_by_month(12),
        'top_users_by_loans': top_users_by_loans(limit),
    }


def report_rows(report_name, limit=50):
    report_map = {
        'most_reserved_books': most_reserved_books,
        'most_read_authors': most_read_authors,
        'loans_by_month': loans_by_month,
        'top_users_by_loans': top_users_by_loans,
    }
    if report_name not in report_map:
        raise ValueError('Reporte no soportado.')
    return report_map[report_name](limit)


def render_csv(report_name, rows):
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow([REPORT_LABELS[report_name]])

    if rows:
        headers = list(rows[0].keys())
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row.get(header, '') for header in headers])
    else:
        writer.writerow(['Sin datos'])

    return buffer.getvalue()


def render_pdf(report_name, rows):
    lines = [REPORT_LABELS[report_name], '']
    if rows:
        headers = list(rows[0].keys())
        lines.append(' | '.join(headers))
        for row in rows:
            lines.append(' | '.join(str(row.get(header, '')) for header in headers))
    else:
        lines.append('Sin datos')

    content = '\\n'.join(lines).replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    stream = f'BT /F1 11 Tf 50 780 Td 14 TL ({content}) Tj ET'.encode('latin-1', 'replace')
    objects = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
        b'<< /Length ' + str(len(stream)).encode() + b' >>\\nstream\\n' + stream + b'\\nendstream',
    ]
    pdf = bytearray(b'%PDF-1.4\\n')
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f'{index} 0 obj\\n'.encode())
        pdf.extend(obj)
        pdf.extend(b'\\nendobj\\n')
    xref = len(pdf)
    pdf.extend(f'xref\\n0 {len(objects) + 1}\\n'.encode())
    pdf.extend(b'0000000000 65535 f \\n')
    for offset in offsets[1:]:
        pdf.extend(f'{offset:010d} 00000 n \\n'.encode())
    pdf.extend(
        f'trailer << /Size {len(objects) + 1} /Root 1 0 R >>\\nstartxref\\n{xref}\\n%%EOF'.encode()
    )
    return bytes(pdf)
