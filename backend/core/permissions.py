from rest_framework.permissions import BasePermission


class RolePermission(BasePermission):
    """Allow only the roles listed in `view.allowed_roles`.

    Views without `allowed_roles` accept any authenticated user because
    IsAuthenticated remains in DEFAULT_PERMISSION_CLASSES.
    """

    def has_permission(self, request, view):
        allowed = getattr(view, "allowed_roles", None)
        if not allowed:
            return True
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role in allowed
        )
