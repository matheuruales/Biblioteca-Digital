from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import User


def is_active_library_user(user):
    return (
        user
        and user.is_authenticated
        and user.is_active
        and user.status == User.STATUS_ACTIVE
    )


class IsActiveAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return is_active_library_user(request.user)


class IsLibrarian(BasePermission):
    def has_permission(self, request, view):
        return is_active_library_user(request.user) and request.user.is_librarian


class IsLibrarianOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if not is_active_library_user(request.user):
            return False

        if request.method in SAFE_METHODS:
            return True

        return request.user.is_librarian
