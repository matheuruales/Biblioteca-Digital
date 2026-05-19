from rest_framework.permissions import BasePermission

from accounts.permissions import is_active_library_user

from .services import user_has_active_sanction


class IsActiveAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return is_active_library_user(request.user)


class IsActiveNonSanctioned(BasePermission):
    message = 'Usuario con sanción activa.'

    def has_permission(self, request, view):
        if not is_active_library_user(request.user):
            return False
        return not user_has_active_sanction(request.user)

