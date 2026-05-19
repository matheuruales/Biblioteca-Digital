from django_filters import rest_framework as filters

from .models import Book


class BookFilter(filters.FilterSet):
    title = filters.CharFilter(field_name='title', lookup_expr='icontains')
    author = filters.NumberFilter(field_name='authors__id')
    category = filters.NumberFilter(field_name='categories__id')
    availability = filters.ChoiceFilter(
        choices=(('available', 'Disponible'), ('unavailable', 'No disponible')),
        method='filter_availability',
    )

    class Meta:
        model = Book
        fields = ('title', 'author', 'category', 'availability')

    def filter_availability(self, queryset, name, value):
        if value == 'available':
            return queryset.filter(available_copies__gt=0)
        if value == 'unavailable':
            return queryset.filter(available_copies=0)
        return queryset
