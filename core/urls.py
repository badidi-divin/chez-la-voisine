from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Auth & Structure
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('', views.redirect_dashboard, name='redirect_dashboard'),

    # Espace Serveur
    path('serveur/dashboard/', views.serveur_dashboard, name='serveur_dashboard'),
    path('serveur/nouvelle-commande/', views.nouvelle_commande, name='nouvelle_commande'),
    path('serveur/historique/', views.serveur_historique, name='serveur_historique'),

    # Espace Caissier
    path('caissier/dashboard/', views.caissier_dashboard, name='caissier_dashboard'),
    path('caissier/valider/<int:commande_id>/', views.valider_paiement, name='valider_paiement'),
    path('caissier/historique/', views.caissier_historique, name='caissier_historique'),
    path('caissier/imprimer/<int:commande_id>/', views.imprimer_recu, name='imprimer_recu'),

    # Espace Admin
    path('admin-custom/dashboard/', views.admin_dashboard, name='admin_dashboard'),
]