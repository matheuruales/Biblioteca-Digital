from django.contrib import admin

from .models import Author, Book, Category


@admin.register(Author)
class AuthorAdmin(admin.ModelAdmin):
    list_display = ('name', 'birth_date', 'death_date')
    search_fields = ('name',)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'isbn', 'total_copies', 'available_copies', 'is_available')
    list_filter = ('categories', 'authors')
    search_fields = ('title', 'isbn', 'authors__name', 'categories__name')
    filter_horizontal = ('authors', 'categories')
