from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BookStateView, LoanViewSet, ReservationViewSet, SanctionViewSet


router = DefaultRouter()
router.register('reservations', ReservationViewSet, basename='reservations')
router.register('loans', LoanViewSet, basename='loans')
router.register('sanctions', SanctionViewSet, basename='sanctions')

urlpatterns = [
    path('books/<int:book_id>/state/', BookStateView.as_view(), name='book_state'),
    path('', include(router.urls)),
]
