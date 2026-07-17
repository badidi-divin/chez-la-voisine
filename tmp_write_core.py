from pathlib import Path

files = {
    'core/views.py': '''import json

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import Categorie, Produit, Commande, LigneCommande, ReservationStock


def get_group_names(user):
    return [group.name.lower() for group in user.groups.all()]


def get_user_role(user):
    if user.is_superuser:
        return 'Dieu'
    groups = get_group_names(user)
    if 'serveur' in groups or 'serveurs' in groups:
        return 'Serveur'
    if 'traiteur' in groups or 'traiteurs' in groups:
        return 'Traiteur'
    if 'caissier' in groups or 'caissiers' in groups:
        return 'Caissier'
    return 'Utilisateur'


def is_allowed_role(user, accepted_roles):
    if user.is_superuser:
        return True
    groups = get_group_names(user)
    return any(role.lower() in groups for role in accepted_roles)


def render_with_role(request, template, context=None):
    if context is None:
        context = {}
    context['user_role'] = get_user_role(request.user)
    return render(request, template, context)


def connexion_unique(request):
    if request.user.is_authenticated:
        return rediriger_selon_role(request.user)

    if request.method == 'POST':
        nom_utilisateur = request.POST.get('username')
        mot_de_passe = request.POST.get('password')
        user = authenticate(request, username=nom_utilisateur, password=mot_de_passe)
        if user is not None:
            login(request, user)
            messages.success(request, f"Bienvenue {user.username} !")
            return rediriger_selon_role(user)
        messages.error(request, "Identifiants incorrects. Réessayez.")

    return render(request, 'authentification/connexion.html')


def rediriger_selon_role(user):
    if user.is_superuser:
        return redirect('page_superuser')
    groups = get_group_names(user)
    if 'serveur' in groups or 'serveurs' in groups:
        return redirect('page_serveur')
    if 'traiteur' in groups or 'traiteurs' in groups:
        return redirect('page_traiteur')
    if 'caissier' in groups or 'caissiers' in groups:
        return redirect('page_caissier')
    return redirect('connexion_unique')


def deconnexion_portail(request):
    logout(request)
    messages.info(request, "Vous avez été déconnecté.")
    return redirect('connexion_unique')


def get_session_key(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


@login_required(login_url='connexion_unique')
def page_superuser(request):
    if not request.user.is_superuser:
        return HttpResponseForbidden('Accès réservé au superutilisateur.')

    total_commandes = Commande.objects.count()
    total_clients = Commande.objects.values('table').distinct().count()
    total_ca = Commande.objects.filter(statut='PAYEE').aggregate(total=Sum('total_montant'))['total'] or 0
    total_produits = LigneCommande.objects.count()
    commandes_recues = Commande.objects.select_related('serveur', 'traiteur', 'caissier').all()[:20]

    return render_with_role(request, 'superuser/dashboard.html', {
        'total_commandes': total_commandes,
        'total_clients': total_clients,
        'total_ca': total_ca,
        'total_produits': total_produits,
        'commandes_recues': commandes_recues,
    })


@login_required(login_url='connexion_unique')
def page_serveur(request):
    if not is_allowed_role(request.user, ['serveur']):
        return HttpResponseForbidden('Accès serveur uniquement.')

    commandes_actives = Commande.objects.filter(
        serveur=request.user,
        statut__in=['EN_ATTENTE', 'EN_PREPARATION', 'PRET']
    ).select_related('traiteur').order_by('date_creation')

    commandes_history = Commande.objects.filter(
        serveur=request.user
    ).order_by('-date_creation')[:10]

    chiffre_affaires = Commande.objects.filter(
        serveur=request.user,
        statut='PAYEE'
    ).aggregate(total=Sum('total_montant'))['total'] or 0

    ready_alerts = commandes_actives.filter(statut='PRET').count()

    return render_with_role(request, 'serveur/tableau_bord.html', {
        'commandes_actives': commandes_actives,
        'commandes_history': commandes_history,
        'chiffre_affaires': chiffre_affaires,
        'ready_alerts': ready_alerts,
    })


@login_required(login_url='connexion_unique')
def page_traiteur(request):
    if not is_allowed_role(request.user, ['traiteur']):
        return HttpResponseForbidden('Accès cuisine uniquement.')

    commandes_cuisine = Commande.objects.filter(
        statut__in=['EN_ATTENTE', 'EN_PREPARATION']
    ).select_related('serveur', 'traiteur').prefetch_related('lignes__produit')

    commandes_history = Commande.objects.filter(
        traiteur=request.user
    ).order_by('-date_creation')[:15]

    total_prepares = Commande.objects.filter(
        traiteur=request.user,
        statut__in=['PRET', 'PAYEE']
    ).count()

    return render_with_role(request, 'traiteur/cuisine.html', {
        'commandes_cuisine': commandes_cuisine,
        'commandes_history': commandes_history,
        'total_prepares': total_prepares,
    })


@login_required(login_url='connexion_unique')
def page_caissier(request):
    if not is_allowed_role(request.user, ['caissier']):
        return HttpResponseForbidden('Accès caisse uniquement.')

    commandes_non_payees = Commande.objects.exclude(statut='PAYEE').select_related('serveur').order_by('date_creation')
    total_attendu = commandes_non_payees.aggregate(total=Sum('total_montant'))['total'] or 0

    return render_with_role(request, 'caissier/tableau_bord.html', {
        'commandes_non_payees': commandes_non_payees,
        'total_attendu': total_attendu,
    })


@login_required(login_url='connexion_unique')
def historique(request):
    role = get_user_role(request.user)

    if request.user.is_superuser:
        commandes = Commande.objects.select_related('serveur', 'traiteur', 'caissier').order_by('-date_creation')[:25]
        total_ca = Commande.objects.filter(statut='PAYEE').aggregate(total=Sum('total_montant'))['total'] or 0
        total_lignes = LigneCommande.objects.count()
        context = {
            'commandes': commandes,
            'stats_label': 'Historique global du restaurant',
            'total_ca': total_ca,
            'total_lignes': total_lignes,
            'user_role': 'Dieu',
            'global_view': True,
        }
    elif role == 'Serveur':
        commandes = Commande.objects.filter(serveur=request.user).order_by('-date_creation')[:25]
        total_ca = Commande.objects.filter(serveur=request.user, statut='PAYEE').aggregate(total=Sum('total_montant'))['total'] or 0
        context = {
            'commandes': commandes,
            'stats_label': 'Chiffre d’affaires généré',
            'total_ca': total_ca,
            'user_role': role,
            'global_view': False,
        }
    elif role == 'Traiteur':
        commandes = Commande.objects.filter(traiteur=request.user).order_by('-date_creation')[:25]
        total_prepares = commandes.filter(statut__in=['PRET', 'PAYEE']).count()
        context = {
            'commandes': commandes,
            'stats_label': 'Plats préparés',
            'total_prepares': total_prepares,
            'user_role': role,
            'global_view': False,
        }
    elif role == 'Caissier':
        commandes = Commande.objects.filter(caissier=request.user).order_by('-date_creation')[:25]
        total_encaisse = Commande.objects.filter(caissier=request.user, statut='PAYEE').aggregate(total=Sum('total_montant'))['total'] or 0
        context = {
            'commandes': commandes,
            'stats_label': 'Fonds encaissés',
            'total_encaisse': total_encaisse,
            'user_role': role,
            'global_view': False,
        }
    else:
        commandes = Commande.objects.none()
        context = {
            'commandes': commandes,
            'stats_label': 'Aucune donnée disponible',
            'user_role': 'Utilisateur',
            'global_view': False,
        }

    return render(request, 'commun/historique.html', context)


@login_required(login_url='connexion_unique')
def traiteur_action(request, commande_id, action):
    if not is_allowed_role(request.user, ['traiteur']):
        return HttpResponseForbidden('Accès cuisine uniquement.')

    commande = get_object_or_404(Commande, pk=commande_id)
    if request.method != 'POST':
        return HttpResponseBadRequest('Méthode POST requise.')

    if action == 'preparer' and commande.statut == 'EN_ATTENTE':
        commande.statut = 'EN_PREPARATION'
        commande.traiteur = request.user
        commande.save(update_fields=['statut', 'traiteur', 'date_modification'])
        messages.success(request, f"Commande #{commande.id} en préparation.")
    elif action == 'pret' and commande.statut == 'EN_PREPARATION':
        commande.statut = 'PRET'
        commande.traiteur = request.user
        commande.save(update_fields=['statut', 'traiteur', 'date_modification'])
        messages.success(request, f"Commande #{commande.id} marquée prête.")
    else:
        messages.warning(request, "Action non valide pour cette commande.")

    return redirect('page_traiteur')


@login_required(login_url='connexion_unique')
def valider_encaissement(request, commande_id):
    if not is_allowed_role(request.user, ['caissier']):
        return HttpResponseForbidden('Accès caisse uniquement.')

    commande = get_object_or_404(Commande, pk=commande_id)
    if request.method != 'POST':
        return HttpResponseBadRequest('Méthode POST requise.')

    if commande.statut != 'PRET':
        messages.warning(request, "La commande n'est pas prête à être payée.")
        return redirect('page_caissier')

    commande.statut = 'PAYEE'
    commande.caissier = request.user
    commande.save(update_fields=['statut', 'caissier', 'date_modification'])
    messages.success(request, f"Encaissement validé pour la commande #{commande.id}.")
    return redirect('page_caissier')


@login_required(login_url='connexion_unique')
def prise_commande_serveur(request):
    if not is_allowed_role(request.user, ['serveur']):
        return HttpResponseForbidden('Accès serveur uniquement.')

    categories = Categorie.objects.all().order_by('nom')
    produits = Produit.objects.filter(disponible=True).select_related('categorie').order_by('nom')
    return render_with_role(request, 'serveur/prise_commande.html', {
        'categories': categories,
        'produits': produits,
    })


@login_required(login_url='connexion_unique')
def get_product_data(request, pk):
    if request.method != 'GET':
        return HttpResponseBadRequest('GET requis.')

    produit = get_object_or_404(Produit, pk=pk, disponible=True)
    session_key = get_session_key(request)
    reserved_by_others = produit.reserved_by_others(session_key=session_key)
    available_stock = produit.available_stock_for_session(session_key=session_key)

    status = 'available'
    if produit.stock_actuel == 0:
        status = 'out_of_stock'
    elif available_stock <= 0:
        status = 'reserved'

    return JsonResponse({
        'id': produit.id,
        'nom': produit.nom,
        'description': produit.description,
        'prix': float(produit.prix),
        'categorie_nom': produit.categorie.nom,
        'stock_actuel': produit.stock_actuel,
        'reserved_by_others': reserved_by_others,
        'available_stock': available_stock,
        'status': status,
    })


@login_required(login_url='connexion_unique')
def reserver_stock(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST requis.')

    session_key = get_session_key(request)
    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest('JSON invalide.')

    action = payload.get('action')
    produit_id = payload.get('product_id')
    produit = get_object_or_404(Produit, pk=produit_id)
    reservation = ReservationStock.objects.filter(produit=produit, session_key=session_key).first()
    reserved_by_others = produit.reserved_by_others(session_key=session_key)

    if action == 'reserve':
        quantity = int(payload.get('quantity', 0))
        if quantity <= 0:
            return JsonResponse({'success': False, 'error': 'Quantité non valide.'})
        max_allowed = produit.stock_actuel - reserved_by_others
        if quantity > max_allowed:
            return JsonResponse({'success': False, 'error': f"Il ne reste que {max_allowed} exemplaire(s) disponible."})

        if reservation:
            reservation.quantite = quantity
            reservation.serveur = request.user
            reservation.save()
        else:
            ReservationStock.objects.create(
                produit=produit,
                session_key=session_key,
                serveur=request.user,
                quantite=quantity,
            )

        return JsonResponse({'success': True, 'available_stock': max_allowed})

    if action == 'release':
        if reservation:
            reservation.delete()
        return JsonResponse({'success': True})

    return HttpResponseBadRequest('Action inconnue.')


@login_required(login_url='connexion_unique')
def valider_commande(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST requis.')

    if not is_allowed_role(request.user, ['serveur']):
        return HttpResponseForbidden('Accès serveur uniquement.')

    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest('JSON invalide.')

    table = payload.get('table')
    panier = payload.get('panier', [])
    session_key = get_session_key(request)

    if not table:
        return JsonResponse({'success': False, 'error': 'Table manquante.'})
    if not isinstance(panier, list) or not panier:
        return JsonResponse({'success': False, 'error': 'Le panier est vide.'})

    commande = Commande.objects.create(
        serveur=request.user,
        table=table,
        statut='EN_ATTENTE',
    )

    try:
        for item in panier:
            produit = get_object_or_404(Produit, pk=item.get('id'))
            quantite = int(item.get('quantite', 0))
            if quantite <= 0:
                raise ValueError('Quantité invalide.')

            reservation = ReservationStock.objects.filter(produit=produit, session_key=session_key).first()
            if reservation and quantite > reservation.quantite:
                raise ValueError(f"Quantité réservée insuffisante pour {produit.nom}.")

            ligne = LigneCommande(
                commande=commande,
                produit=produit,
                quantite=quantite,
                prix_unitaire=produit.prix,
            )
            ligne.save()

        ReservationStock.objects.filter(session_key=session_key).delete()
        commande.update_total()
        return JsonResponse({'success': True})
    except Exception as exc:
        commande.delete()
        return JsonResponse({'success': False, 'error': str(exc)})
''',
    'core/urls.py': '''from django.urls import path
from . import views

urlpatterns = [
    path('', views.connexion_unique, name='home'),
    path('connexion/', views.connexion_unique, name='connexion_unique'),
    path('deconnexion/', views.deconnexion_portail, name='deconnexion_portail'),
    path('superuser/', views.page_superuser, name='page_superuser'),
    path('serveur/', views.page_serveur, name='page_serveur'),
    path('serveur/nouvelle-commande/', views.prise_commande_serveur, name='prise_commande_serveur'),
    path('serveur/nouvelle-commande/product/<int:pk>/', views.get_product_data, name='get_product_data'),
    path('serveur/nouvelle-commande/reserver/', views.reserver_stock, name='reservation_stock'),
    path('serveur/nouvelle-commande/valider/', views.valider_commande, name='valider_commande'),
    path('traiteur/', views.page_traiteur, name='page_traiteur'),
    path('traiteur/action/<int:commande_id>/<str:action>/', views.traiteur_action, name='traiteur_action'),
    path('caissier/', views.page_caissier, name='page_caissier'),
    path('caissier/valider/<int:commande_id>/', views.valider_encaissement, name='valider_encaissement'),
    path('historique/', views.historique, name='historique'),
]
''',
    'core/admin.py': '''from django.contrib import admin
from django.utils.html import format_html
from .models import Categorie, Produit, Commande, LigneCommande, ReservationStock


def formater_fc(valeur):
    if valeur is None:
        return "0 FC"
    return f"{int(valeur):,}".replace(",", " ") + " FC"


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ('nom', 'categorie', 'prix_affiche', 'prix', 'stock_actuel', 'statut_stock', 'disponible')
    list_filter = ('categorie', 'disponible')
    search_fields = ('nom',)
    list_editable = ('prix', 'stock_actuel', 'disponible')

    def prix_affiche(self, obj):
        return formater_fc(obj.prix)
    prix_affiche.short_description = "Prix de vente"
    prix_affiche.admin_order_field = "prix"

    def statut_stock(self, obj):
        if obj.stock_actuel == 0:
            return format_html('<span style="color: red; font-weight: bold;">🔴 Rupture de stock</span>')
        if obj.en_alerte:
            return format_html('<span style="color: orange; font-weight: bold;">⚠️ Stock critique ({})</span>', obj.stock_actuel)
        return format_html('<span style="color: green;">🟢 En stock</span>')
    statut_stock.short_description = "État du stock"


class LigneCommandeInline(admin.TabularInline):
    model = LigneCommande
    extra = 1
    readonly_fields = ('prix_unitaire_affiche', 'sous_total_affiche')
    fields = ('produit', 'quantite', 'prix_unitaire_affiche', 'sous_total_affiche', 'est_pret')

    def prix_unitaire_affiche(self, obj):
        if obj.id:
            return formater_fc(obj.prix_unitaire)
        return '-'
    prix_unitaire_affiche.short_description = "Prix unitaire"

    def sous_total_affiche(self, obj):
        if obj.id:
            return formater_fc(obj.sous_total)
        return '-'
    sous_total_affiche.short_description = "Sous-total"


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ('id', 'table', 'serveur', 'traiteur', 'caissier', 'statut_badge', 'total_calcule', 'date_creation')
    list_filter = ('statut', 'date_creation', 'serveur', 'traiteur', 'caissier')
    search_fields = ('id', 'table', 'serveur__username', 'traiteur__username', 'caissier__username')
    inlines = [LigneCommandeInline]

    def statut_badge(self, obj):
        couleurs = {
            'EN_ATTENTE': '#ffc107',
            'EN_PREPARATION': '#0d6efd',
            'PRET': '#198754',
            'PAYEE': '#6c757d',
            'ANNULE': '#dc3545',
        }
        color = couleurs.get(obj.statut, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 4px 8px; border-radius: 6px;">{}</span>',
            color,
            obj.get_statut_display()
        )
    statut_badge.short_description = "Statut"

    def total_calcule(self, obj):
        return formater_fc(obj.total_montant)
    total_calcule.short_description = "Montant total"
    total_calcule.admin_order_field = 'total_montant'


@admin.register(ReservationStock)
class ReservationStockAdmin(admin.ModelAdmin):
    list_display = ('produit', 'serveur', 'session_key', 'quantite', 'updated_at')
    search_fields = ('produit__nom', 'serveur__username', 'session_key')
    list_filter = ('serveur',)
''',
    'core/templates/base.html': '''<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Gestion Restaurant{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        body { background: #f8f9fa; }
        .navbar-brand span { font-weight: 700; }
        .flash-badge { animation: blink 1.4s infinite; }
        @keyframes blink { 0%,100% { opacity: 1; } 50% { opacity: 0.2; } }
        .dark-mode { background: #12131a; color: #f8f9fa; }
        .dark-mode .card { background: #1f2330; border-color: #32394f; }
    </style>
    {% block extra_styles %}{% endblock %}
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-dark shadow-sm">
    <div class="container-fluid">
        <a class="navbar-brand" href="{% url 'home' %}"><span>La Voisine</span></a>
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
            <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse" id="navbarNav">
            <ul class="navbar-nav me-auto mb-2 mb-lg-0">
                {% if user.is_authenticated %}
                    {% if user.is_superuser %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'page_superuser' %}">Admin</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'page_serveur' %}">Serveur</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'page_traiteur' %}">Cuisine</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'page_caissier' %}">Caisse</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'historique' %}">Stats Globales</a></li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="{% url 'page_serveur' %}">Mon Dashboard</a></li>
                        <li class="nav-item"><a class="nav-link" href="{% url 'historique' %}">Historique</a></li>
                    {% endif %}
                {% endif %}
            </ul>
            <div class="d-flex align-items-center gap-3">
                {% if user.is_authenticated %}
                    <div class="text-white small text-end">
                        <div>{{ user.username|capfirst }}</div>
                        <div>{{ user_role }}</div>
                    </div>
                    <a class="btn btn-outline-light btn-sm" href="{% url 'deconnexion_portail' %}">
                        <i class="fa-solid fa-right-from-bracket"></i> Déconnexion
                    </a>
                {% endif %}
            </div>
        </div>
    </div>
</nav>
<div class="container py-4">
    {% if messages %}
        <div class="mb-3">
            {% for message in messages %}
                <div class="alert alert-{{ message.tags }} alert-dismissible fade show" role="alert">
                    {{ message }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                </div>
            {% endfor %}
        </div>
    {% endif %}
    {% block content %}{% endblock %}
</div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
{% block extra_scripts %}{% endblock %}
</body>
</html>
''',
    'core/templates/authentification/connexion.html': '''{% extends 'base.html' %}
{% block title %}Connexion - La Voisine{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6 col-lg-5">
        <div class="card shadow-sm">
            <div class="card-body p-4">
                <h3 class="card-title mb-3">Connexion</h3>
                <p class="text-muted">Accédez à votre espace selon votre rôle.</p>
                <form method="post">{% csrf_token %}
                    <div class="mb-3">
                        <label class="form-label">Nom d'utilisateur</label>
                        <input type="text" name="username" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label class="form-label">Mot de passe</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <button class="btn btn-dark w-100">Se connecter</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
''',
    'core/templates/serveur/tableau_bord.html': '''{% extends 'base.html' %}
{% block title %}Dashboard Serveur{% endblock %}
{% block content %}
<div class="row mb-4">
    <div class="col-md-8">
        <div class="card shadow-sm">
            <div class="card-body">
                <h4 class="card-title">Commandes en cours</h4>
                {% if ready_alerts %}
                    <div class="alert alert-success flash-badge">{{ ready_alerts }} commande(s) PRÊTE(S) !</div>
                {% endif %}
                {% if commandes_actives %}
                    <div class="list-group">
                        {% for commande in commandes_actives %}
                            <div class="list-group-item d-flex justify-content-between align-items-start">
                                <div>
                                    <div class="fw-bold">Commande #{{ commande.id }} - Table {{ commande.table }}</div>
                                    <small class="text-muted">Statut : {{ commande.get_statut_display }}</small><br>
                                    <small>Préparée par : {{ commande.traiteur.username|default:'En attente' }}</small>
                                </div>
                                <span class="badge bg-{{ 'success' if commande.statut == 'PRET' else 'warning' if commande.statut == 'EN_PREPARATION' else 'secondary' }}">
                                    {{ commande.get_statut_display }}
                                </span>
                            </div>
                        {% endfor %}
                    </div>
                {% else %}
                    <p class="text-muted">Aucune commande active pour le moment.</p>
                {% endif %}
            </div>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card shadow-sm mb-4">
            <div class="card-body">
                <h5 class="card-title">Résumé</h5>
                <p class="mb-2">Chiffre d’affaires : <strong>{{ chiffre_affaires|default:0 }} FC</strong></p>
                <p class="mb-0">Commandes récentes :</p>
                {% if commandes_history %}
                    <ul class="list-group list-group-flush mt-2">
                        {% for commande in commandes_history %}
                            <li class="list-group-item py-2">
                                #{{ commande.id }} - {{ commande.table }}
                                <span class="badge bg-secondary float-end">{{ commande.get_statut_display }}</span>
                            </li>
                        {% endfor %}
                    </ul>
                {% else %}
                    <p class="text-muted">Aucune commande passée.</p>
                {% endif %}
            </div>
        </div>
        <a class="btn btn-dark w-100 mb-2" href="{% url 'prise_commande_serveur' %}"><i class="fa-solid fa-cart-plus me-2"></i> Prendre une commande</a>
        <a class="btn btn-outline-secondary w-100" href="{% url 'historique' %}"><i class="fa-solid fa-clock-rotate-left me-2"></i> Mon historique</a>
    </div>
</div>
{% endblock %}
''',
    'core/templates/traiteur/cuisine.html': '''{% extends 'base.html' %}
{% block title %}Cuisine / Traiteur{% endblock %}
{% block extra_styles %}
<style>.dark-mode body{background:#10121a;color:#e8ebf3;}.dark-mode .card{background:#161b2b;border-color:#2d3349;}.dark-mode .btn-outline-light{color:#f8f9fa;border-color:#f8f9fa;}</style>
{% endblock %}
{% block content %}
<div class="dark-mode p-3 rounded-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <div>
            <h3>Interface Cuisine</h3>
            <p class="text-white-50">Commandes en attente de préparation et en cours.</p>
        </div>
        <div class="text-end">
            <div class="text-white-50">Plats préparés</div>
            <div class="fs-4 fw-bold">{{ total_prepares }}</div>
        </div>
    </div>
    {% if commandes_cuisine %}
        <div class="row g-3">
            {% for commande in commandes_cuisine %}
                <div class="col-12">
                    <div class="card shadow-sm">
                        <div class="card-body">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <h5 class="mb-1">Commande #{{ commande.id }} - Table {{ commande.table }}</h5>
                                    <small class="text-muted">Envoyé par : {{ commande.serveur.username|default:'Serveur inconnu' }}</small>
                                </div>
                                <span class="badge bg-{{ 'warning' if commande.statut == 'EN_ATTENTE' else 'info' }}">
                                    {{ commande.get_statut_display }}
                                </span>
                            </div>
                            <div class="mb-3">
                                <strong>Lignes :</strong>
                                <ul class="list-unstyled mb-0">
                                    {% for ligne in commande.lignes.all %}
                                        <li>{{ ligne.quantite }}x {{ ligne.produit.nom }} {% if ligne.est_pret %}<span class="badge bg-success">Prêt</span>{% endif %}</li>
                                    {% endfor %}
                                </ul>
                            </div>
                            <div class="d-flex gap-2">
                                {% if commande.statut == 'EN_ATTENTE' %}
                                    <form method="post" action="{% url 'traiteur_action' commande.id 'preparer' %}">{% csrf_token %}
                                        <button class="btn btn-light btn-sm">Lancer la préparation</button>
                                    </form>
                                {% endif %}
                                {% if commande.statut == 'EN_PREPARATION' %}
                                    <form method="post" action="{% url 'traiteur_action' commande.id 'pret' %}">{% csrf_token %}
                                        <button class="btn btn-success btn-sm">Marquer prêt</button>
                                    </form>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                </div>
            {% endfor %}
        </div>
    {% else %}
        <div class="alert alert-light">Aucune commande en attente pour la cuisine.</div>
    {% endif %}
</div>
{% endblock %}
''',
    'core/templates/caissier/tableau_bord.html': '''{% extends 'base.html' %}
{% block title %}Dashboard Caissier{% endblock %}
{% block content %}
<div class="row">
    <div class="col-lg-8">
        <div class="card shadow-sm mb-4">
            <div class="card-body">
                <h4 class="card-title">Commandes en attente d'encaissement</h4>
                {% if commandes_non_payees %}
                    <div class="table-responsive">
                        <table class="table align-middle mb-0">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Table</th>
                                    <th>Serveur</th>
                                    <th>Montant</th>
                                    <th>Statut</th>
                                    <th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {% for commande in commandes_non_payees %}
                                    <tr>
                                        <td>{{ commande.id }}</td>
                                        <td>{{ commande.table }}</td>
                                        <td>{{ commande.serveur.username|default:'-' }}</td>
                                        <td>{{ commande.total_montant }} FC</td>
                                        <td>{{ commande.get_statut_display }}</td>
                                        <td>
                                            <form method="post" action="{% url 'valider_encaissement' commande.id %}">{% csrf_token %}
                                                <button class="btn btn-success btn-sm">Valider l'encaissement</button>
                                            </form>
                                        </td>
                                    </tr>
                                {% endfor %}
                            </tbody>
                        </table>
                    </div>
                {% else %}
                    <p class="text-muted">Pas de commande à encaisser actuellement.</p>
                {% endif %}
            </div>
        </div>
    </div>
    <div class="col-lg-4">
        <div class="card shadow-sm">
            <div class="card-body">
                <h5>Total attendu</h5>
                <div class="fs-3 fw-bold">{{ total_attendu }} FC</div>
                <p class="text-muted">Toutes les commandes non payées sont affichées ci-dessus.</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
''',
    'core/templates/commun/historique.html': '''{% extends 'base.html' %}
{% block title %}Historique{% endblock %}
{% block content %}
<div class="row mb-4">
    <div class="col-md-8">
        <div class="card shadow-sm">
            <div class="card-body">
                <h4 class="card-title">{{ stats_label }}</h4>
                {% if user_role == 'Dieu' %}
                    <p class="text-muted">Chiffre d'affaires global : <strong>{{ total_ca }} FC</strong></p>
                    <p class="text-muted">Commandes totales : <strong>{{ commandes.count }}</strong></p>
                    <p class="text-muted">Lignes de commandes totales : <strong>{{ total_lignes }}</strong></p>
                {% elif user_role == 'Serveur' %}
                    <p class="text-muted">CA généré : <strong>{{ total_ca }} FC</strong></p>
                {% elif user_role == 'Traiteur' %}
                    <p class="text-muted">Plats préparés : <strong>{{ total_prepares }}</strong></p>
                {% elif user_role == 'Caissier' %}
                    <p class="text-muted">Fonds encaissés : <strong>{{ total_encaisse }} FC</strong></p>
                {% endif %}
            </div>
        </div>
    </div>
</div>
<div class="card shadow-sm">
    <div class="card-body">
        <h5 class="card-title">Détail des commandes</h5>
        {% if commandes %}
            <div class="table-responsive">
                <table class="table table-hover align-middle">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Table</th>
                            <th>Statut</th>
                            <th>Serveur</th>
                            <th>Traiteur</th>
                            <th>Caissier</th>
                            <th>Total</th>
                            <th>Date</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for commande in commandes %}
                            <tr>
                                <td>{{ commande.id }}</td>
                                <td>{{ commande.table }}</td>
                                <td>{{ commande.get_statut_display }}</td>
                                <td>{{ commande.serveur.username|default:'-' }}</td>
                                <td>{{ commande.traiteur.username|default:'-' }}</td>
                                <td>{{ commande.caissier.username|default:'-' }}</td>
                                <td>{{ commande.total_montant }} FC</td>
                                <td>{{ commande.date_creation|date:'d/m/Y H:i' }}</td>
                            </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        {% else %}
            <p class="text-muted">Aucune entrée historique disponible.</p>
        {% endif %}
    </div>
</div>
{% endblock %}
''',
    'core/templates/superuser/dashboard.html': '''{% extends 'base.html' %}
{% block title %}Dashboard Superutilisateur{% endblock %}
{% block content %}
<div class="row g-4">
    <div class="col-md-3">
        <div class="card shadow-sm text-center p-3">
            <h5>Total commandes</h5>
            <div class="fs-2 fw-bold">{{ total_commandes }}</div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card shadow-sm text-center p-3">
            <h5>Tables actives</h5>
            <div class="fs-2 fw-bold">{{ total_clients }}</div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card shadow-sm text-center p-3">
            <h5>CA global</h5>
            <div class="fs-2 fw-bold">{{ total_ca }} FC</div>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card shadow-sm text-center p-3">
            <h5>Produits vendus</h5>
            <div class="fs-2 fw-bold">{{ total_produits }}</div>
        </div>
    </div>
</div>
<div class="card shadow-sm mt-4">
    <div class="card-body">
        <h5 class="card-title">Commandes récentes</h5>
        <div class="table-responsive">
            <table class="table align-middle mb-0">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Table</th>
                        <th>Serveur</th>
                        <th>Traiteur</th>
                        <th>Caissier</th>
                        <th>Statut</th>
                        <th>Total</th>
                    </tr>
                </thead>
                <tbody>
                    {% for commande in commandes_recues %}
                        <tr>
                            <td>{{ commande.id }}</td>
                            <td>{{ commande.table }}</td>
                            <td>{{ commande.serveur.username|default:'-' }}</td>
                            <td>{{ commande.traiteur.username|default:'-' }}</td>
                            <td>{{ commande.caissier.username|default:'-' }}</td>
                            <td>{{ commande.get_statut_display }}</td>
                            <td>{{ commande.total_montant }} FC</td>
                        </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>
{% endblock %}
''',
    'core/templates/serveur/prise_commande.html': '''{% extends 'base.html' %}
{% block title %}Prise de commande{% endblock %}
{% block extra_styles %}
<style>.product-card:hover{transform:translateY(-2px);transition:transform .15s ease;}</style>
{% endblock %}
{% block content %}
<div class="row g-4">
    <div class="col-lg-7">
        <div class="card shadow-sm p-3">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div>
                    <h4>Recherche produit</h4>
                    <p class="text-muted mb-0">Sélectionnez un produit et réservez le stock avant d’ajouter au panier.</p>
                </div>
                <span class="badge bg-secondary" id="resultsCount">0 résultats</span>
            </div>
            <div class="mb-3">
                <input id="searchInput" type="search" class="form-control" placeholder="Rechercher par nom, catégorie ou prix..." oninput="renderSearchResults()">
            </div>
            <div class="row g-3" id="searchResults"></div>
        </div>
        <div class="card shadow-sm p-3 mt-3 d-none" id="productDetails">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <div>
                    <h5 id="detailName"></h5>
                    <p class="text-muted mb-0" id="detailCategory"></p>
                </div>
                <span id="detailBadge" class="badge"></span>
            </div>
            <p id="detailDescription" class="text-muted"></p>
            <div class="d-flex gap-3 align-items-center mb-3">
                <div>
                    <div class="text-muted small">Prix</div>
                    <div id="detailPrice" class="fs-4 fw-bold"></div>
                </div>
                <div>
                    <div class="text-muted small">Stock dispo</div>
                    <div id="detailStock" class="fs-4 fw-bold"></div>
                </div>
            </div>
            <div class="d-flex align-items-center gap-2 mb-3">
                <button class="btn btn-outline-secondary" type="button" onclick="changeDetailQuantity(-1)">-</button>
                <input id="detailQuantity" type="number" min="1" value="1" class="form-control text-center" style="width: 80px;" onchange="onQuantityInput()">
                <button class="btn btn-outline-secondary" type="button" onclick="changeDetailQuantity(1)">+</button>
                <button id="addToCartButton" class="btn btn-dark" type="button" onclick="addToCart()">Ajouter au panier</button>
            </div>
            <div id="detailAlert" class="alert alert-warning d-none"></div>
        </div>
    </div>
    <div class="col-lg-5">
        <div class="card shadow-sm p-3">
            <h4>Panier</h4>
            <div id="cartItemsListSidebar" class="list-group list-group-flush mb-3">
                <p class="text-center text-muted py-5">Le panier est vide.</p>
            </div>
            <div class="d-flex justify-content-between align-items-center mb-3">
                <span>Total actuel</span>
                <span id="cartTotal">0</span> FC
            </div>
            <button id="submitOrderButton" class="btn btn-success w-100" onclick="envoyerCommande()" disabled>Envoyer la commande</button>
        </div>
    </div>
</div>
<div class="modal fade" id="cartModal" tabindex="-1" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Résumé du panier</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div id="cartItemsList"></div>
                <div class="mt-3 d-flex justify-content-between align-items-center">
                    <span>Total</span>
                    <strong id="modalTotal">0 FC</strong>
                </div>
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Fermer</button>
                <button type="button" class="btn btn-success" onclick="envoyerCommande()">Valider</button>
            </div>
        </div>
    </div>
</div>
<script>
    const produits = JSON.parse('{{ produits|safe }}');
    const productDetailUrl = "{% url 'get_product_data' 0 %}";
    const reserveUrl = "{% url 'reservation_stock' %}";
    const validateOrderUrl = "{% url 'valider_commande' %}";
    let selectedProduct = null;
    let cart = [];

    function renderSearchResults() {
        const query = document.getElementById('searchInput').value.trim().toLowerCase();
        const results = produits.filter(prod => {
            const text = `${prod.nom} ${prod.categorie.nom} ${prod.prix}`.toLowerCase();
            return text.includes(query);
        });
        const container = document.getElementById('searchResults');
        container.innerHTML = '';
        document.getElementById('resultsCount').innerText = `${results.length} résultat(s)`;
        if (!results.length) {
            container.innerHTML = '<div class="text-center text-muted py-4">Aucun produit trouvé.</div>';
            return;
        }
        results.forEach(prod => {
            const card = document.createElement('div');
            card.className = 'col-sm-6';
            card.innerHTML = `
                <div class="card product-card h-100" onclick="selectProduct(${prod.id})" style="cursor:pointer;">
                    <div class="card-body">
                        <h6 class="card-title">${prod.nom}</h6>
                        <p class="card-text text-muted mb-1">${prod.categorie.nom}</p>
                        <p class="fw-bold mb-0">${prod.prix} FC</p>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    }

    function selectProduct(productId) {
        fetch(productDetailUrl.replace('0/', `${productId}/`))
            .then(resp => resp.json())
            .then(data => showProductDetail(data))
            .catch(() => alert('Impossible de charger le produit.'));
    }

    function showProductDetail(product) {
        selectedProduct = product;
        document.getElementById('detailName').innerText = product.nom;
        document.getElementById('detailCategory').innerText = product.categorie_nom;
        document.getElementById('detailPrice').innerText = `${product.prix} FC`;
        document.getElementById('detailDescription').innerText = product.description || 'Aucune description.';
        document.getElementById('detailStock').innerText = product.available_stock;
        document.getElementById('detailQuantity').value = 1;
        const badge = document.getElementById('detailBadge');
        badge.className = 'badge';
        badge.classList.add(product.status === 'out_of_stock' ? 'bg-danger' : product.status === 'reserved' ? 'bg-warning text-dark' : 'bg-success');
        badge.innerText = product.status === 'out_of_stock' ? 'Épuisé' : product.status === 'reserved' ? 'Réservé' : 'En stock';
        document.getElementById('addToCartButton').disabled = product.status !== 'available';
        document.getElementById('productDetails').classList.remove('d-none');
    }

    function changeDetailQuantity(delta) {
        const input = document.getElementById('detailQuantity');
        let value = parseInt(input.value, 10) + delta;
        if (value < 1) value = 1;
        if (selectedProduct && value > selectedProduct.available_stock) {
            value = selectedProduct.available_stock;
            showDetailWarning('Quantité maximale atteinte.');
        }
        input.value = value;
    }

    function onQuantityInput() {
        const input = document.getElementById('detailQuantity');
        if (!selectedProduct) return;
        let value = parseInt(input.value, 10);
        if (isNaN(value) || value < 1) value = 1;
        if (value > selectedProduct.available_stock) {
            value = selectedProduct.available_stock;
            showDetailWarning('Quantité maximale atteinte.');
        }
        input.value = value;
    }

    function showDetailWarning(message) {
        const alert = document.getElementById('detailAlert');
        alert.innerText = message;
        alert.classList.remove('d-none');
    }

    function reserveStock(productId, quantity) {
        return fetch(reserveUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': '{{ csrf_token }}'
            },
            body: JSON.stringify({action:'reserve', product_id:productId, quantity})
        }).then(r => r.json());
    }

    function addToCart() {
        if (!selectedProduct) return;
        const quantity = parseInt(document.getElementById('detailQuantity').value, 10);
        if (quantity < 1) {
            showDetailWarning('Quantité invalide.');
            return;
        }

        reserveStock(selectedProduct.id, quantity).then(result => {
            if (!result.success) {
                showDetailWarning(result.error || 'Erreur de réservation.');
                return;
            }
            const item = cart.find(i => i.id === selectedProduct.id);
            if (item) {
                item.quantite = quantity;
            } else {
                cart.push({id:selectedProduct.id, nom:selectedProduct.nom, prix:selectedProduct.prix, quantite:quantity});
            }
            updateCartUI();
        });
    }

    function updateCartUI() {
        const cartList = document.getElementById('cartItemsListSidebar');
        const cartModalList = document.getElementById('cartItemsList');
        let total = 0;
        let html = '';
        cart.forEach(item => {
            total += item.prix * item.quantite;
            html += `
                <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                    <div>
                        <strong>${item.nom}</strong><br>
                        <small>${item.prix} FC x ${item.quantite}</small>
                    </div>
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-sm btn-outline-secondary" onclick="changeCartQty(${item.id}, -1)"><i class="fa-solid fa-minus"></i></button>
                        <button type="button" class="btn btn-sm btn-outline-secondary" onclick="changeCartQty(${item.id}, 1)"><i class="fa-solid fa-plus"></i></button>
                        <button type="button" class="btn btn-sm btn-outline-danger" onclick="removeFromCart(${item.id})"><i class="fa-solid fa-trash"></i></button>
                    </div>
                </div>
            `;
        });
        if (!html) html = '<p class="text-center text-muted py-4">Le panier est vide.</p>';
        cartList.innerHTML = html;
        cartModalList.innerHTML = html;
        document.getElementById('cartTotal').innerText = total;
        document.getElementById('modalTotal').innerText = `${total} FC`;
        document.getElementById('submitOrderButton').disabled = cart.length === 0;
    }

    function changeCartQty(productId, delta) {
        const item = cart.find(i => i.id === productId);
        if (!item) return;
        const newQty = item.quantite + delta;
        if (newQty <= 0) {
            removeFromCart(productId);
            return;
        }
        reserveStock(productId, newQty).then(result => {
            if (!result.success) {
                alert(result.error || 'Impossible de modifier la quantité.');
                return;
            }
            item.quantite = newQty;
            updateCartUI();
        });
    }

    function removeFromCart(productId) {
        fetch(reserveUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': '{{ csrf_token }}'
            },
            body: JSON.stringify({action:'release', product_id:productId})
        }).then(() => {
            cart = cart.filter(i => i.id !== productId);
            updateCartUI();
        });
    }

    function envoyerCommande() {
        if (!cart.length) {
            alert('Le panier est vide.');
            return;
        }
        const table = prompt('Indiquez le numéro de table / emplacement :', 'Table 1');
        if (!table) return;
        fetch(validateOrderUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': '{{ csrf_token }}'
            },
            body: JSON.stringify({table, panier: cart})
        }).then(r => r.json()).then(result => {
            if (result.success) {
                alert('Commande envoyée avec succès.');
                cart = [];
                updateCartUI();
            } else {
                alert(result.error || 'Erreur lors de l’envoi.');
            }
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        renderSearchResults();
        updateCartUI();
    });
</script>
''',
}

base_dir = Path('c:/Users/Divin BADIDI/Desktop/gestion_bar_restaurant')
for relative, content in files.items():
    path = base_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')

# also create authentification and needed template dirs
for folder in ['core/templates/commun', 'core/templates/superuser', 'core/templates/serveur', 'core/templates/traiteur', 'core/templates/caissier', 'core/templates/authentification']:
    (base_dir / folder).mkdir(parents=True, exist_ok=True)
''