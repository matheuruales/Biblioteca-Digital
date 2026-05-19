from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from catalog.models import Author, Book, Category
from circulation.models import Loan, Reservation, Sanction
from circulation.services import (
    calculate_overdue_days,
    send_loan_email,
    send_reservation_email,
    upsert_sanction_for_loan,
)
from reports.services import REPORT_LABELS, all_reports, dashboard_summary, render_csv, render_pdf, report_rows

from .forms import (
    AuthorForm,
    BookForm,
    CategoryForm,
    LoanForm,
    LoginForm,
    ReaderRegistrationForm,
    ReservationForm,
    UserCreateForm,
    UserUpdateForm,
)


User = get_user_model()


def is_active_user(user):
    return user.is_authenticated and user.is_active and user.status == User.STATUS_ACTIVE


def is_librarian(user):
    return is_active_user(user) and user.is_librarian


def is_reader(user):
    return is_active_user(user) and user.role == User.ROLE_READER


def role_dashboard_url(user):
    if user.is_librarian:
        return reverse('library_web:librarian_dashboard')
    return reverse('library_web:reader_dashboard')


def role_home(request):
    if not request.user.is_authenticated:
        return redirect('library_web:login')
    return redirect(role_dashboard_url(request.user))


def redirect_if_cross_role_area(request):
    if request.path.startswith('/lector/') and not is_reader(request.user):
        messages.error(request, 'Esta vista es para lectores.')
        return role_home(request)
    if request.path.startswith('/bibliotecario/') and not is_librarian(request.user):
        messages.error(request, 'Acceso restringido a bibliotecarios.')
        return role_home(request)
    return None


class LibrarianRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_librarian(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, 'Acceso restringido a bibliotecarios.')
        return redirect('library_web:home')


class ReaderRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return is_reader(self.request.user)

    def handle_no_permission(self):
        messages.error(self.request, 'Esta vista es para lectores.')
        return redirect('library_web:home')


class RoleTemplateMixin:
    base_template = None

    def get_base_template(self):
        if self.base_template:
            return self.base_template
        if self.request.user.is_authenticated and self.request.user.is_librarian:
            return 'library_web/base_librarian.html'
        return 'library_web/base_reader.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = self.get_base_template()
        return context


def home(request):
    return role_home(request)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('library_web:dashboard')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.cleaned_data['user'])
        messages.success(request, 'Sesion iniciada correctamente.')
        return redirect(role_dashboard_url(form.cleaned_data['user']))

    return render(request, 'library_web/login.html', {'form': form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect('library_web:dashboard')

    form = ReaderRegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Registro completado.')
        return redirect('library_web:reader_dashboard')

    return render(request, 'library_web/register.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.success(request, 'Sesion cerrada.')
    return redirect('library_web:login')


@login_required
def dashboard_view(request):
    return role_home(request)


@login_required
def reader_dashboard_view(request):
    if request.user.status != User.STATUS_ACTIVE:
        logout(request)
        messages.error(request, 'Usuario bloqueado o inactivo.')
        return redirect('library_web:login')
    if not request.user.role == User.ROLE_READER:
        return redirect('library_web:librarian_dashboard')

    summary = dashboard_summary()
    context = {
        'summary': summary,
        'available_books': Book.objects.prefetch_related('authors').filter(available_copies__gt=0).order_by('title')[:6],
        'my_loans': Loan.objects.select_related('book').filter(user=request.user).order_by('-loaned_at')[:5],
        'my_reservations': Reservation.objects.select_related('book').filter(user=request.user).order_by('-reserved_at')[:5],
        'my_sanctions': Sanction.objects.select_related('loan', 'loan__book').filter(user=request.user).order_by('-created_at')[:5],
    }
    return render(request, 'library_web/reader_dashboard.html', context)


@login_required
def librarian_dashboard_view(request):
    if not is_librarian(request.user):
        messages.error(request, 'Acceso restringido a bibliotecarios.')
        return role_home(request)
    summary = dashboard_summary()
    reports = all_reports(5)
    context = {
        'summary': summary,
        'reports': reports,
        'report_labels': REPORT_LABELS,
        'recent_loans': Loan.objects.select_related('book', 'user').order_by('-loaned_at')[:6],
        'recent_reservations': Reservation.objects.select_related('book', 'user').order_by('-reserved_at')[:6],
    }
    return render(request, 'library_web/librarian_dashboard.html', context)


@login_required
def export_report_view(request, file_format):
    if not is_librarian(request.user):
        messages.error(request, 'Acceso restringido a bibliotecarios.')
        return role_home(request)
    report_name = request.GET.get('report', 'loans_by_month')
    if report_name not in REPORT_LABELS:
        messages.error(request, 'Reporte no soportado.')
        return redirect('library_web:librarian_dashboard')

    rows = report_rows(report_name, 100)
    filename = f'{report_name}.{file_format}'
    if file_format == 'csv':
        response = HttpResponse(render_csv(report_name, rows), content_type='text/csv')
    elif file_format == 'pdf':
        response = HttpResponse(render_pdf(report_name, rows), content_type='application/pdf')
    else:
        messages.error(request, 'Formato no soportado.')
        return redirect('library_web:librarian_dashboard')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def librarian_reports_view(request):
    if not is_librarian(request.user):
        messages.error(request, 'Acceso restringido a bibliotecarios.')
        return role_home(request)
    context = {
        'summary': dashboard_summary(),
        'reports': all_reports(10),
        'report_labels': REPORT_LABELS,
    }
    return render(request, 'library_web/report_list.html', context)


class UserListView(RoleTemplateMixin, LibrarianRequiredMixin, ListView):
    model = User
    template_name = 'library_web/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.order_by('username')
        search = self.request.GET.get('search')
        role = self.request.GET.get('role')
        status = self.request.GET.get('status')
        if search:
            qs = qs.filter(Q(username__icontains=search) | Q(email__icontains=search))
        if role:
            qs = qs.filter(role=role)
        if status:
            qs = qs.filter(status=status)
        return qs


class UserCreateView(RoleTemplateMixin, LibrarianRequiredMixin, CreateView):
    model = User
    form_class = UserCreateForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:user_list')
    extra_context = {'title': 'Crear usuario', 'submit_label': 'Crear'}


class UserUpdateView(RoleTemplateMixin, LibrarianRequiredMixin, UpdateView):
    model = User
    form_class = UserUpdateForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:user_list')
    extra_context = {'title': 'Editar usuario', 'submit_label': 'Guardar'}


class UserDeleteView(RoleTemplateMixin, LibrarianRequiredMixin, DeleteView):
    model = User
    template_name = 'library_web/confirm_delete.html'
    success_url = reverse_lazy('library_web:user_list')


class AuthorListView(RoleTemplateMixin, LoginRequiredMixin, ListView):
    model = Author
    template_name = 'library_web/author_list.html'
    context_object_name = 'authors'

    def get_queryset(self):
        qs = Author.objects.order_by('name')
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        return qs


class LibrarianAuthorListView(LibrarianRequiredMixin, AuthorListView):
    pass


class AuthorCreateView(RoleTemplateMixin, LibrarianRequiredMixin, CreateView):
    model = Author
    form_class = AuthorForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:author_list')
    extra_context = {'title': 'Crear autor', 'submit_label': 'Crear'}


class AuthorUpdateView(RoleTemplateMixin, LibrarianRequiredMixin, UpdateView):
    model = Author
    form_class = AuthorForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:author_list')
    extra_context = {'title': 'Editar autor', 'submit_label': 'Guardar'}


class AuthorDeleteView(RoleTemplateMixin, LibrarianRequiredMixin, DeleteView):
    model = Author
    template_name = 'library_web/confirm_delete.html'
    success_url = reverse_lazy('library_web:author_list')


class CategoryListView(RoleTemplateMixin, LoginRequiredMixin, ListView):
    model = Category
    template_name = 'library_web/category_list.html'
    context_object_name = 'categories'

    def get_queryset(self):
        qs = Category.objects.order_by('name')
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        return qs


class LibrarianCategoryListView(LibrarianRequiredMixin, CategoryListView):
    pass


class CategoryCreateView(RoleTemplateMixin, LibrarianRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:category_list')
    extra_context = {'title': 'Crear categoria', 'submit_label': 'Crear'}


class CategoryUpdateView(RoleTemplateMixin, LibrarianRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:category_list')
    extra_context = {'title': 'Editar categoria', 'submit_label': 'Guardar'}


class CategoryDeleteView(RoleTemplateMixin, LibrarianRequiredMixin, DeleteView):
    model = Category
    template_name = 'library_web/confirm_delete.html'
    success_url = reverse_lazy('library_web:category_list')


class BookListView(RoleTemplateMixin, LoginRequiredMixin, ListView):
    model = Book
    template_name = 'library_web/book_list.html'
    context_object_name = 'books'
    paginate_by = 20

    def get_queryset(self):
        qs = Book.objects.prefetch_related('authors', 'categories').order_by('title')
        search = self.request.GET.get('search')
        author = self.request.GET.get('author')
        category = self.request.GET.get('category')
        availability = self.request.GET.get('availability')
        if search:
            qs = qs.filter(
                Q(title__icontains=search)
                | Q(isbn__icontains=search)
                | Q(authors__name__icontains=search)
                | Q(categories__name__icontains=search)
            )
        if author:
            qs = qs.filter(authors__id=author)
        if category:
            qs = qs.filter(categories__id=category)
        if availability == 'available':
            qs = qs.filter(available_copies__gt=0)
        elif availability == 'unavailable':
            qs = qs.filter(available_copies=0)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['authors'] = Author.objects.order_by('name')
        context['categories'] = Category.objects.order_by('name')
        return context


class ReaderBookListView(ReaderRequiredMixin, BookListView):
    base_template = 'library_web/base_reader.html'


class LibrarianBookListView(LibrarianRequiredMixin, BookListView):
    pass


class BookCreateView(RoleTemplateMixin, LibrarianRequiredMixin, CreateView):
    model = Book
    form_class = BookForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:book_list')
    extra_context = {'title': 'Crear libro', 'submit_label': 'Crear'}


class BookUpdateView(RoleTemplateMixin, LibrarianRequiredMixin, UpdateView):
    model = Book
    form_class = BookForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:book_list')
    extra_context = {'title': 'Editar libro', 'submit_label': 'Guardar'}


class BookDeleteView(RoleTemplateMixin, LibrarianRequiredMixin, DeleteView):
    model = Book
    template_name = 'library_web/confirm_delete.html'
    success_url = reverse_lazy('library_web:book_list')


class ReservationListView(RoleTemplateMixin, LoginRequiredMixin, ListView):
    model = Reservation
    template_name = 'library_web/reservation_list.html'
    context_object_name = 'reservations'

    def get_queryset(self):
        qs = Reservation.objects.select_related('user', 'book').order_by('-reserved_at')
        if not self.request.user.is_librarian:
            qs = qs.filter(user=self.request.user)
        return qs


class ReaderReservationListView(ReaderRequiredMixin, ReservationListView):
    base_template = 'library_web/base_reader.html'


class LibrarianReservationListView(LibrarianRequiredMixin, ReservationListView):
    pass


class ReservationCreateView(RoleTemplateMixin, LoginRequiredMixin, CreateView):
    model = Reservation
    form_class = ReservationForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:reservation_list')
    extra_context = {'title': 'Crear reserva', 'submit_label': 'Reservar'}

    def dispatch(self, request, *args, **kwargs):
        cross_role_redirect = redirect_if_cross_role_area(request)
        if cross_role_redirect:
            return cross_role_redirect
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['current_user'] = self.request.user
        return kwargs

    def get_success_url(self):
        if self.request.user.is_librarian:
            return reverse('library_web:reservation_list')
        return reverse('library_web:reader_reservation_list')

    def get_initial(self):
        initial = super().get_initial()
        book_id = self.request.GET.get('book')
        if book_id:
            initial['book'] = book_id
        return initial

    def form_valid(self, form):
        try:
            with transaction.atomic():
                book = Book.objects.select_for_update().get(pk=form.cleaned_data['book'].pk)
                if book.available_copies <= 0:
                    form.add_error(None, 'No hay copias disponibles para reservar.')
                    return self.form_invalid(form)
                reservation = form.save(commit=False)
                reservation.user = form.cleaned_data['user']
                reservation.book = book
                reservation.save()
                book.available_copies -= 1
                book.save(update_fields=['available_copies'])
        except IntegrityError:
            form.add_error(None, 'Ya existe una reserva activa para este libro.')
            return self.form_invalid(form)
        send_reservation_email(reservation)
        messages.success(self.request, 'Reserva registrada.')
        return redirect(self.get_success_url())


@login_required
def cancel_reservation_view(request, pk):
    cross_role_redirect = redirect_if_cross_role_area(request)
    if cross_role_redirect:
        return cross_role_redirect

    reservation = get_object_or_404(Reservation.objects.select_related('book'), pk=pk)
    redirect_url = 'library_web:reservation_list' if request.user.is_librarian else 'library_web:reader_reservation_list'
    if not request.user.is_librarian and reservation.user != request.user:
        messages.error(request, 'No puedes cancelar esta reserva.')
        return redirect(redirect_url)
    if reservation.status == Reservation.STATUS_ACTIVE:
        with transaction.atomic():
            reservation.status = Reservation.STATUS_CANCELED
            reservation.canceled_at = timezone.now()
            reservation.save(update_fields=['status', 'canceled_at'])
            reservation.book.available_copies += 1
            reservation.book.save(update_fields=['available_copies'])
        messages.success(request, 'Reserva cancelada.')
    return redirect(redirect_url)


class LoanListView(RoleTemplateMixin, LoginRequiredMixin, ListView):
    model = Loan
    template_name = 'library_web/loan_list.html'
    context_object_name = 'loans'

    def get_queryset(self):
        qs = Loan.objects.select_related('user', 'book').order_by('-loaned_at')
        if not self.request.user.is_librarian:
            qs = qs.filter(user=self.request.user)
        return qs


class ReaderLoanListView(ReaderRequiredMixin, LoanListView):
    base_template = 'library_web/base_reader.html'


class LibrarianLoanListView(LibrarianRequiredMixin, LoanListView):
    pass


class LoanCreateView(RoleTemplateMixin, LibrarianRequiredMixin, CreateView):
    model = Loan
    form_class = LoanForm
    template_name = 'library_web/form.html'
    success_url = reverse_lazy('library_web:loan_list')
    extra_context = {'title': 'Registrar prestamo', 'submit_label': 'Prestar'}

    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.cleaned_data['user']
                book = Book.objects.select_for_update().get(pk=form.cleaned_data['book'].pk)
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
                        form.add_error(None, 'No hay copias disponibles para prestar.')
                        return self.form_invalid(form)
                    book.available_copies -= 1
                    book.save(update_fields=['available_copies'])

                loan = form.save(commit=False)
                loan.created_by = self.request.user
                loan.book = book
                loan.save()
        except IntegrityError:
            form.add_error(None, 'Ya existe un prestamo abierto para este usuario y libro.')
            return self.form_invalid(form)
        send_loan_email(loan)
        messages.success(self.request, 'Prestamo registrado.')
        return redirect(self.success_url)


@login_required
def return_loan_view(request, pk):
    if not is_librarian(request.user):
        messages.error(request, 'Acceso restringido a bibliotecarios.')
        return role_home(request)
    loan = get_object_or_404(Loan.objects.select_related('book', 'user'), pk=pk)
    if loan.status in (Loan.STATUS_RETURNED, Loan.STATUS_RETURNED_LATE):
        messages.info(request, 'Este prestamo ya fue devuelto.')
        return redirect('library_web:loan_list')

    with transaction.atomic():
        loan.returned_at = timezone.now()
        overdue_days = calculate_overdue_days(loan, at_time=loan.returned_at)
        loan.status = Loan.STATUS_RETURNED_LATE if overdue_days > 0 else Loan.STATUS_RETURNED
        loan.save(update_fields=['status', 'returned_at'])
        loan.book.available_copies += 1
        loan.book.save(update_fields=['available_copies'])
        if overdue_days > 0:
            upsert_sanction_for_loan(loan, at_time=loan.returned_at)
    messages.success(request, 'Prestamo devuelto.')
    return redirect('library_web:loan_list')


class SanctionListView(LoginRequiredMixin, ListView):
    model = Sanction
    template_name = 'library_web/sanction_list.html'
    context_object_name = 'sanctions'

    def get_queryset(self):
        qs = Sanction.objects.select_related('user', 'loan', 'loan__book').order_by('-created_at')
        if not self.request.user.is_librarian:
            qs = qs.filter(user=self.request.user)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['base_template'] = (
            'library_web/base_librarian.html'
            if self.request.user.is_librarian
            else 'library_web/base_reader.html'
        )
        return context


class ReaderSanctionListView(ReaderRequiredMixin, SanctionListView):
    pass


class LibrarianSanctionListView(LibrarianRequiredMixin, SanctionListView):
    pass
