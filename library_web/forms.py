from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from catalog.models import Author, Book, Category
from circulation.models import Loan, Reservation
from circulation.services import default_reservation_expires_at, user_has_active_sanction


User = get_user_model()


class LoginForm(forms.Form):
    username = forms.CharField(label='Usuario')
    password = forms.CharField(label='Contrasena', widget=forms.PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password = cleaned_data.get('password')
        user = authenticate(username=username, password=password)

        if user is None:
            raise ValidationError('Usuario o contrasena invalidos.')
        if not user.is_active or user.status != User.STATUS_ACTIVE:
            raise ValidationError('Usuario inactivo o bloqueado.')

        cleaned_data['user'] = user
        return cleaned_data


class ReaderRegistrationForm(UserCreationForm):
    email = forms.EmailField(label='Correo')
    first_name = forms.CharField(label='Nombre', required=False)
    last_name = forms.CharField(label='Apellido', required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Ya existe un usuario con este correo.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email'].lower()
        user.role = User.ROLE_READER
        user.status = User.STATUS_ACTIVE
        if commit:
            user.save()
        return user


class UserCreateForm(UserCreationForm):
    email = forms.EmailField(label='Correo')

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'status')


class UserUpdateForm(forms.ModelForm):
    password = forms.CharField(
        label='Nueva contrasena',
        required=False,
        widget=forms.PasswordInput,
        help_text='Deja este campo vacio para mantener la contrasena actual.',
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'status', 'password')

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class AuthorForm(forms.ModelForm):
    class Meta:
        model = Author
        fields = ('name', 'biography', 'birth_date', 'death_date')
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
            'death_date': forms.DateInput(attrs={'type': 'date'}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('name', 'description')


class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = (
            'title',
            'isbn',
            'description',
            'publication_date',
            'authors',
            'categories',
            'total_copies',
            'available_copies',
        )
        widgets = {
            'publication_date': forms.DateInput(attrs={'type': 'date'}),
            'authors': forms.CheckboxSelectMultiple,
            'categories': forms.CheckboxSelectMultiple,
        }

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get('total_copies')
        available = cleaned_data.get('available_copies')
        if total is not None and available is not None and available > total:
            raise ValidationError('Las copias disponibles no pueden superar el total.')
        return cleaned_data


class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ('user', 'book', 'expires_at')
        widgets = {
            'expires_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, current_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_user = current_user
        self.fields['book'].queryset = Book.objects.filter(available_copies__gt=0).order_by('title')
        self.fields['expires_at'].initial = default_reservation_expires_at().strftime('%Y-%m-%dT%H:%M')

        if current_user and not current_user.is_librarian:
            self.fields.pop('user')
        else:
            self.fields['user'].queryset = User.objects.filter(status=User.STATUS_ACTIVE).order_by('username')

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user') or self.current_user
        book = cleaned_data.get('book')
        expires_at = cleaned_data.get('expires_at')

        if user and user_has_active_sanction(user):
            raise ValidationError('Usuario con sancion activa.')
        if book and book.available_copies <= 0:
            raise ValidationError('No hay copias disponibles para reservar.')
        if expires_at and expires_at <= timezone.now():
            raise ValidationError('La fecha de expiracion debe ser futura.')
        cleaned_data['user'] = user
        return cleaned_data


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ('user', 'book', 'due_at')
        widgets = {
            'due_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.filter(status=User.STATUS_ACTIVE).order_by('username')
        self.fields['book'].queryset = Book.objects.order_by('title')

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        book = cleaned_data.get('book')
        due_at = cleaned_data.get('due_at')

        if user and user_has_active_sanction(user):
            raise ValidationError('Usuario con sancion activa.')
        if book and book.available_copies <= 0:
            has_reservation = Reservation.objects.filter(
                user=user,
                book=book,
                status=Reservation.STATUS_ACTIVE,
                expires_at__gt=timezone.now(),
            ).exists()
            if not has_reservation:
                raise ValidationError('No hay copias disponibles para prestar.')
        if due_at and due_at <= timezone.now():
            raise ValidationError('La fecha de vencimiento debe ser futura.')
        return cleaned_data
