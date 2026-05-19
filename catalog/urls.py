from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AuthorViewSet, BookViewSet, CategoryViewSet


router = DefaultRouter()
router.register('authors', AuthorViewSet, basename='authors')
router.register('categories', CategoryViewSet, basename='categories')
router.register('books', BookViewSet, basename='books')

urlpatterns = [
    path('', include(router.urls)),
]
