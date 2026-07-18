from django.urls import path
from . import views

urlpatterns = [
    # Page d'accueil racine redirige vers le portail de connexion
    path('', views.connexion_unique, name='home'),
    path('connexion/', views.connexion_unique, name='connexion_unique'),
    path('deconnexion/', views.deconnexion_portail, name='deconnexion_portail'),
    # Le serveur arrive d'abord ici :
    path('serveur/', views.page_serveur, name='page_serveur'),
    path('serveur/historique/', views.page_serveur_historique, name='page_serveur_historique'),
    
    # Puis clique pour aller ici :
    path('serveur/nouvelle-commande/', views.prise_commande_serveur, name='prise_commande_serveur'),
    path('serveur/nouvelle-commande/product/<int:pk>/', views.get_product_data, name='get_product_data'),
    path('serveur/nouvelle-commande/reserver/', views.reserver_stock, name='reservation_stock'),
    path('serveur/nouvelle-commande/valider/', views.valider_commande, name='valider_commande'),

    # Espace Traiteur
    path('traiteur/', views.page_traiteur, name='page_traiteur'),
    path('traiteur/commandes/', views.page_traiteur_commandes, name='page_traiteur_commandes'),
    path('traiteur/historique/', views.page_traiteur_historique, name='page_traiteur_historique'),
    path('traiteur/commande/<int:pk>/statut/', views.changer_statut_commande, name='changer_statut_commande'),

    # Espace Caissier
    path('caissier/', views.page_caissier, name='page_caissier'),
    path('caissier/historique/', views.page_caissier_historique, name='page_caissier_historique'),
    path('caissier/commande/<int:pk>/paiement/', views.valider_paiement_commande, name='valider_paiement_commande'),
    path('caissier/commande/<int:pk>/recu/', views.recu_paiement_commande, name='recu_paiement_commande'),
]