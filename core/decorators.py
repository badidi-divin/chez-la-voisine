from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def role_required(*allowed_roles):
    """
    Vérifie si l'utilisateur connecté appartient à au moins un des groupes autorisés,
    ou s'il est Superutilisateur (Admin).
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            # L'admin a accès à tout
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Vérification des groupes
            user_groups = request.user.groups.values_list('name', flat=True)
            if any(role in user_groups for role in allowed_roles):
                return view_func(request, *args, **kwargs)
            
            messages.error(request, "Accès non autorisé à cet espace.")
            return redirect('redirect_dashboard')
        return _wrapped_view
    return decorator