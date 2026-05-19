from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.text import slugify


class Author(models.Model):
    name = models.CharField(max_length=150)
    biography = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)
    death_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)

    def clean(self):
        if self.birth_date and self.death_date and self.death_date < self.birth_date:
            raise ValidationError({'death_date': 'La fecha de muerte no puede ser anterior al nacimiento.'})

    def __str__(self):
        return self.name


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        verbose_name_plural = 'categories'

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or 'category'
            candidate = base_slug
            suffix = 2

            while Category.objects.exclude(pk=self.pk).filter(slug=candidate).exists():
                candidate = f'{base_slug}-{suffix}'
                suffix += 1

            self.slug = candidate

        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Book(models.Model):
    title = models.CharField(max_length=200)
    isbn = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    publication_date = models.DateField(null=True, blank=True)
    authors = models.ManyToManyField(Author, related_name='books', blank=True)
    categories = models.ManyToManyField(Category, related_name='books', blank=True)
    total_copies = models.PositiveIntegerField(default=1)
    available_copies = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('title',)
        constraints = (
            models.CheckConstraint(
                condition=Q(total_copies__gte=0),
                name='book_total_copies_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(available_copies__gte=0),
                name='book_available_copies_non_negative',
            ),
            models.CheckConstraint(
                condition=Q(available_copies__lte=models.F('total_copies')),
                name='book_available_not_greater_than_total',
            ),
        )

    @property
    def is_available(self):
        return self.available_copies > 0

    def clean(self):
        if self.available_copies > self.total_copies:
            raise ValidationError(
                {'available_copies': 'Las copias disponibles no pueden superar el total.'}
            )

    def __str__(self):
        return self.title
