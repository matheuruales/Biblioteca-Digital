from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from accounts.permissions import IsLibrarianOrReadOnly

from .filters import BookFilter
from .models import Author, Book, Category
from .serializers import AuthorSerializer, BookSerializer, CategorySerializer


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
    permission_classes = (IsLibrarianOrReadOnly,)
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('name',)
    ordering_fields = ('id', 'name', 'created_at')


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = (IsLibrarianOrReadOnly,)
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')
    filter_backends = (filters.SearchFilter, filters.OrderingFilter)
    search_fields = ('name',)
    ordering_fields = ('id', 'name', 'created_at')


class BookViewSet(viewsets.ModelViewSet):
    serializer_class = BookSerializer
    permission_classes = (IsLibrarianOrReadOnly,)
    http_method_names = ('get', 'post', 'patch', 'delete', 'head', 'options')
    filter_backends = (DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter)
    filterset_class = BookFilter
    search_fields = ('title', 'isbn', 'authors__name', 'categories__name')
    ordering_fields = ('id', 'title', 'isbn', 'created_at', 'publication_date')

    def get_queryset(self):
        return Book.objects.prefetch_related('authors', 'categories').distinct()
