from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """Allow access only to users with role='admin'."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
        )


class IsCustomerUser(permissions.BasePermission):
    """Allow access only to users with role='customer'."""

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'customer'
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Object-level: only the owner can modify; anyone can read."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        # obj must have an 'owner' field pointing to a User
        return obj.owner == request.user


class IsGroundOwner(permissions.BasePermission):
    """Check if user is the owner of the ground."""

    def has_object_permission(self, request, view, obj):
        if hasattr(obj, 'owner'):
            return obj.owner == request.user
        if hasattr(obj, 'ground'):
            return obj.ground.owner == request.user
        return False


class IsBookingParticipant(permissions.BasePermission):
    """Allow access only to the customer who booked or the ground owner."""

    def has_object_permission(self, request, view, obj):
        return (
            obj.customer == request.user
            or obj.ground.owner == request.user
        )


class IsReviewAuthor(permissions.BasePermission):
    """Only the review author can edit/delete."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.customer == request.user
