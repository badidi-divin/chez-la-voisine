import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Count
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden

from .models import Categorie, Produit, Commande, LigneCommande, ReservationStock

# ==========================================================
# 🔑 SYSTÈME D'AUTHENTIFICATION CENTRALISÉ & UNIQUE
# ==========================================================

def connexion_unique(request):
    """
    Portail d'accès unique. Identifie l'utilisateur et l'aiguille
    automatiquement vers son interface de travail selon son groupe.
    """
    # Si l'utilisateur est déjà connecté, on le redirige directement selon son rôle
    if request.user.is_authenticated:
        return rediriger_selon_role(request.user)

    if request.method == 'POST':
        nom_utilisateur = request.POST.get('username')
        mot_de_passe = request.POST.get('password')
        
        # Authentification de l'utilisateur
        user = authenticate(request, username=nom_utilisateur, password=mot_de_passe)
        
        if user is not None:
            login(request, user)
            messages.success(request, f"Ravi de vous revoir, {user.username} !")
            # Redirection automatique selon le rôle
            return rediriger_selon_role(user)
        else:
            messages.error(request, "Identifiants incorrects. Veuillez réessayer.")

    return render(request, 'authentification/connexion.html')


def rediriger_selon_role(user):
    """
    Fonction utilitaire interne pour rediriger l'utilisateur 
    vers son espace de travail selon ses groupes Django.
    """
    if user.is_superuser:
        return redirect('page_admin')
        
    def groupe_present(prefix):
        return user.groups.filter(name__istartswith=prefix).exists()

    if groupe_present('serveur'):
        return redirect('page_serveur')
    elif groupe_present('caissier'):
        return redirect('page_caissier')
    elif groupe_present('traiteur'):
        return redirect('page_traiteur')
    
    # Si l'utilisateur est connecté mais n'a aucun de ces groupes associés, on le déconnecte par sécurité
    return redirect('deconnexion_portail')


def deconnexion_portail(request):
    """Déconnexion globale et redirection vers le portail unique."""
    logout(request)
    messages.info(request, "Vous avez été déconnecté.")
    return redirect('connexion_unique')


def is_traiteur(user):
    return user.groups.filter(name__istartswith='traiteur').exists()


def is_serveur(user):
    return user.groups.filter(name__istartswith='serveur').exists()


def is_caissier(user):
    return user.groups.filter(name__istartswith='caissier').exists()


def is_administrateur(user):
    return user.is_superuser


# ==========================================================
# 🖥️ VUES DES ESPACES UTILISATEURS (PROTÉGÉES)
# ==========================================================

@login_required(login_url='connexion_unique')
def page_serveur(request):
    """
    ÉCRAN 1 : Le Tableau de Bord du Serveur (Statistiques de vente journalières).
    """
    aujourd_hui = timezone.now().date()
    
    # 1. Récupération des commandes du serveur connecté pour AUJOURD'HUI
    # (Ajuste les noms de champs 'serveur' et 'date_creation' selon tes modèles)
    commandes_du_jour = Commande.objects.filter(
        serveur=request.user,
        date_creation__date=aujourd_hui  
    )
    
    # 2. Calcul des statistiques
    total_commandes = commandes_du_jour.count()
    
    # On calcule le chiffre d'affaires sur les commandes payées/validées pour éviter les faux totaux
    ventes_reussies = commandes_du_jour.filter(statut='PAYE')
    
    # Somme des montants sur les lignes de commande (prix × quantité)
    chiffre_affaires = ventes_reussies.aggregate(
        total=Sum(
            ExpressionWrapper(
                F('lignes__prix_unitaire') * F('lignes__quantite'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
    )['total'] or 0

    commandes_en_cours = Commande.objects.filter(
        serveur=request.user,
        statut__in=['EN_ATTENTE', 'EN_PREPARATION', 'PRET']
    ).order_by('-date_creation')

    context = {
        'total_commandes': total_commandes,
        'chiffre_affaires': chiffre_affaires,
        'commandes_en_cours': commandes_en_cours,
        'active_tab': 'accueil',
    }
    return render(request, 'serveur/tableau_bord.html', context)


@login_required(login_url='connexion_unique')
def page_serveur_historique(request):
    """
    ÉCRAN Historique des commandes du serveur.
    """
    commandes_historique = Commande.objects.filter(
        serveur=request.user
    ).order_by('-date_creation')

    total_commandes = commandes_historique.count()
    chiffre_affaires = commandes_historique.filter(statut='PAYE').aggregate(
        total=Sum(
            ExpressionWrapper(
                F('lignes__prix_unitaire') * F('lignes__quantite'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
    )['total'] or 0

    context = {
        'total_commandes': total_commandes,
        'chiffre_affaires': chiffre_affaires,
        'commandes_historique': commandes_historique,
        'active_tab': 'historique',
    }
    return render(request, 'serveur/tableau_bord.html', context)


def get_session_key(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


@login_required(login_url='connexion_unique')
def prise_commande_serveur(request):
    """
    ÉCRAN 2 : Interface pour le Serveur - Prise de commande sur mobile (Vanilla JS).
    """
    if request.method == 'POST':
        return JsonResponse({'success': False, 'error': 'Cette route n’accepte pas de POST direct.'}, status=405)

    categories = Categorie.objects.all()
    produits = Produit.objects.filter(disponible=True).select_related('categorie').order_by('nom')
    products_data = json.dumps([
        {
            'id': prod.id,
            'nom': prod.nom,
            'prix': float(prod.prix),
            'categorie_nom': prod.categorie.nom,
            'categorie_id': prod.categorie_id,
            'stock_actuel': prod.stock_actuel,
            'disponible': prod.disponible,
        }
        for prod in produits
    ], ensure_ascii=False)

    return render(request, 'serveur/prise_commande.html', {
        'categories': categories,
        'products_json': products_data,
        'active_tab': 'nouvelle_commande',
    })


@login_required(login_url='connexion_unique')
def get_product_data(request, pk):
    if request.method != 'GET':
        return HttpResponseBadRequest('GET requis.')

    produit = get_object_or_404(Produit, pk=pk, disponible=True)
    session_key = get_session_key(request)
    reserved_by_others = produit.reserved_by_others(session_key=session_key)
    available_stock = produit.available_stock_for_session(session_key=session_key)
    disponible_par_serveur = available_stock > 0

    if produit.stock_actuel == 0:
        status = 'out_of_stock'
    elif not disponible_par_serveur:
        status = 'reserved'
    else:
        status = 'available'

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

    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest('JSON invalide.')

    action = payload.get('action')
    session_key = get_session_key(request)

    if action == 'clear':
        ReservationStock.objects.filter(session_key=session_key).delete()
        return JsonResponse({'success': True})

    product_id = payload.get('product_id')
    if not product_id:
        return HttpResponseBadRequest('product_id requis.')

    produit = get_object_or_404(Produit, pk=product_id)
    existing = ReservationStock.objects.filter(produit=produit, session_key=session_key).first()
    reserved_by_others = produit.reserved_by_others(session_key=session_key)
    current_quantity = existing.quantite if existing else 0

    if action == 'reserve':
        quantity = int(payload.get('quantity', 0))
        if quantity <= 0:
            return HttpResponseBadRequest('quantity doit être > 0.')

        max_allowed = produit.stock_actuel - reserved_by_others
        if quantity > max_allowed:
            return JsonResponse({
                'success': False,
                'error': f"Désolé, il ne reste que {max_allowed} article(s) en stock",
                'available_stock': max_allowed,
            })

        if existing:
            existing.quantite = quantity
            existing.serveur = request.user
            existing.save()
        else:
            ReservationStock.objects.create(
                produit=produit,
                session_key=session_key,
                serveur=request.user,
                quantite=quantity,
            )

        return JsonResponse({
            'success': True,
            'reserved_quantity': quantity,
            'available_stock': max_allowed,
        })

    if action == 'release':
        quantity = payload.get('quantity')
        if existing is None:
            return JsonResponse({'success': True})
        if quantity is None:
            existing.delete()
            return JsonResponse({'success': True})

        quantity = int(quantity)
        if quantity <= 0:
            existing.delete()
        elif quantity >= existing.quantite:
            existing.delete()
        else:
            existing.quantite = quantity
            existing.save()
        return JsonResponse({'success': True})

    return HttpResponseBadRequest('Action inconnue.')


@login_required(login_url='connexion_unique')
def valider_commande(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('POST requis.')

    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest('JSON invalide.')

    table_reference = payload.get('table')
    panier = payload.get('panier', [])
    session_key = get_session_key(request)

    if not table_reference:
        return JsonResponse({'success': False, 'error': 'Référence de table manquante.'})
    if not isinstance(panier, list) or not panier:
        return JsonResponse({'success': False, 'error': 'Le panier est vide.'})

    commande = Commande.objects.create(
        serveur=request.user,
        table=table_reference,
        statut='EN_ATTENTE'
    )

    try:
        for item in panier:
            produit_id = item.get('id')
            quantite = int(item.get('quantite', 0))
            produit = get_object_or_404(Produit, pk=produit_id)

            if quantite <= 0:
                raise ValueError('Quantité non valide.')

            reservation = ReservationStock.objects.filter(produit=produit, session_key=session_key).first()
            if reservation and quantite > reservation.quantite:
                raise ValueError('Quantité réservée insuffisante pour le produit ' + produit.nom)

            if quantite > produit.available_stock_for_session(session_key=session_key) + (reservation.quantite if reservation else 0):
                raise ValueError(f"Stock insuffisant pour {produit.nom}.")

            ligne = LigneCommande(commande=commande, produit=produit, quantite=quantite, prix_unitaire=produit.prix)
            ligne.save()

        ReservationStock.objects.filter(session_key=session_key).delete()
        return JsonResponse({'success': True})
    except Exception as exc:
        commande.delete()
        return JsonResponse({'success': False, 'error': str(exc)})


@login_required(login_url='connexion_unique')
def page_caissier(request):
    """
    Interface pour le Caissier : Validation des paiements et encaissement.
    """
    if not is_caissier(request.user):
        return redirect('deconnexion_portail')

    commandes_a_payer = Commande.objects.filter(statut='PRET').order_by('date_creation')
    commandes_historique = Commande.objects.filter(statut__in=['PAYEE', 'ANNULE']).order_by('-date_creation')

    chiffre_affaires = commandes_historique.filter(statut='PAYEE').aggregate(
        total=Sum(
            ExpressionWrapper(
                F('lignes__prix_unitaire') * F('lignes__quantite'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
    )['total'] or 0

    context = {
        'commandes_a_payer': commandes_a_payer,
        'commandes_historique': commandes_historique,
        'total_a_payer': commandes_a_payer.count(),
        'total_encaisse': chiffre_affaires,
        'active_tab': 'commandes',
    }
    return render(request, 'caissier/tableau_bord.html', context)


@login_required(login_url='connexion_unique')
def page_caissier_historique(request):
    if not is_caissier(request.user):
        return redirect('deconnexion_portail')

    commandes_historique = Commande.objects.filter(statut__in=['PAYEE', 'ANNULE']).order_by('-date_creation')
    chiffre_affaires = commandes_historique.filter(statut='PAYEE').aggregate(
        total=Sum(
            ExpressionWrapper(
                F('lignes__prix_unitaire') * F('lignes__quantite'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
    )['total'] or 0

    context = {
        'commandes_historique': commandes_historique,
        'total_encaisse': chiffre_affaires,
        'active_tab': 'historique',
    }
    return render(request, 'caissier/tableau_bord.html', context)


@login_required(login_url='connexion_unique')
def valider_paiement_commande(request, pk):
    if not is_caissier(request.user):
        return HttpResponseForbidden('Accès refusé.')
    if request.method != 'POST':
        return HttpResponseBadRequest('POST requis.')

    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest('JSON invalide.')

    action = payload.get('action')
    if action not in ['PAYEE', 'ANNULE']:
        return HttpResponseBadRequest('Action invalide.')

    commande = get_object_or_404(Commande, pk=pk)
    if commande.statut != 'PRET':
        return JsonResponse({'success': False, 'error': 'La commande doit être prête pour validation.'})

    commande.statut = action
    if action == 'PAYEE':
        commande.caissier = request.user
    commande.save(update_fields=['statut', 'caissier', 'date_modification'])

    return JsonResponse({'success': True, 'statut': commande.statut})


@login_required(login_url='connexion_unique')
def recu_paiement_commande(request, pk):
    if not is_caissier(request.user):
        return redirect('deconnexion_portail')

    commande = get_object_or_404(Commande, pk=pk)
    return render(request, 'caissier/recu_paiement.html', {
        'commande': commande,
        'server_name': commande.serveur.username if commande.serveur else '—',
    })


@login_required(login_url='connexion_unique')
def page_admin(request):
    if not is_administrateur(request.user):
        return redirect('deconnexion_portail')

    orders = Commande.objects.select_related('serveur', 'caissier', 'traiteur').all()
    start_date_value = request.GET.get('start_date')
    end_date_value = request.GET.get('end_date')
    start_date = parse_date(start_date_value) if start_date_value else None
    end_date = parse_date(end_date_value) if end_date_value else None
    statut = request.GET.get('statut')
    serveur = request.GET.get('serveur')
    caissier = request.GET.get('caissier')

    if start_date:
        orders = orders.filter(date_creation__date__gte=start_date)
    if end_date:
        orders = orders.filter(date_creation__date__lte=end_date)
    if statut:
        orders = orders.filter(statut=statut)
    if serveur:
        orders = orders.filter(serveur__username=serveur)
    if caissier:
        orders = orders.filter(caissier__username=caissier)

    total_orders = orders.count()
    total_revenue = orders.filter(statut='PAYEE').aggregate(total=Sum('total_montant'))['total'] or 0
    status_counts = orders.values('statut').annotate(count=Count('id')).order_by('statut')
    commandes_globales = orders.order_by('-date_creation')[:200]

    serveurs = User.objects.filter(groups__name__iexact='Serveur').order_by('username').distinct()
    caissiers = User.objects.filter(groups__name__iexact='Caissier').order_by('username').distinct()

    context = {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'status_counts': status_counts,
        'commandes_globales': commandes_globales,
        'status_choices': Commande.STATUT_CHOICES,
        'serveurs': serveurs,
        'caissiers': caissiers,
        'filters': {
            'start_date': request.GET.get('start_date', ''),
            'end_date': request.GET.get('end_date', ''),
            'statut': statut or '',
            'serveur': serveur or '',
            'caissier': caissier or '',
        }
    }
    return render(request, 'admin/dashboard.html', context)


@login_required(login_url='connexion_unique')
def page_traiteur(request):
    """
    Interface Traiteur - Statistiques générales et accès aux commandes.
    """
    if not is_traiteur(request.user):
        return redirect('deconnexion_portail')

    commandes_du_jour = Commande.objects.filter(date_creation__date=timezone.now().date())
    commandes_en_attente = commandes_du_jour.filter(statut='EN_ATTENTE')
    commandes_en_preparation = commandes_du_jour.filter(statut='EN_PREPARATION')
    commandes_pret = commandes_du_jour.filter(statut='PRET')

    chiffre_affaires = commandes_du_jour.filter(statut='PAYEE').aggregate(
        total=Sum(
            ExpressionWrapper(
                F('lignes__prix_unitaire') * F('lignes__quantite'),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        )
    )['total'] or 0

    context = {
        'total_commandes': commandes_du_jour.count(),
        'commandes_en_attente': commandes_en_attente.count(),
        'commandes_en_preparation': commandes_en_preparation.count(),
        'commandes_pret': commandes_pret.count(),
        'chiffre_affaires': chiffre_affaires,
        'commandes': commandes_du_jour.filter(statut__in=['EN_ATTENTE', 'EN_PREPARATION', 'PRET']).order_by('date_creation'),
        'commandes_historique': Commande.objects.exclude(statut='EN_ATTENTE').order_by('-date_creation'),
        'active_tab': 'statistiques',
    }
    return render(request, 'traiteur/cuisine.html', context)


@login_required(login_url='connexion_unique')
def page_traiteur_commandes(request):
    if not is_traiteur(request.user):
        return redirect('deconnexion_portail')

    commandes = Commande.objects.filter(statut__in=['EN_ATTENTE', 'EN_PREPARATION', 'PRET']).order_by('date_creation')
    commandes_historique = Commande.objects.exclude(statut='EN_ATTENTE').order_by('-date_creation')

    context = {
        'commandes': commandes,
        'commandes_historique': commandes_historique,
        'active_tab': 'commandes',
    }
    return render(request, 'traiteur/cuisine.html', context)


@login_required(login_url='connexion_unique')
def page_traiteur_historique(request):
    if not is_traiteur(request.user):
        return redirect('deconnexion_portail')

    commandes_historique = Commande.objects.exclude(statut='EN_ATTENTE').order_by('-date_creation')

    context = {
        'commandes_historique': commandes_historique,
        'active_tab': 'historique',
    }
    return render(request, 'traiteur/cuisine.html', context)


@login_required(login_url='connexion_unique')
def changer_statut_commande(request, pk):
    if not is_traiteur(request.user):
        return HttpResponseForbidden('Accès refusé.')
    if request.method != 'POST':
        return HttpResponseBadRequest('POST requis.')

    try:
        payload = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest('JSON invalide.')

    statut = payload.get('statut')
    if statut not in ['EN_PREPARATION', 'PRET']:
        return HttpResponseBadRequest('Statut invalide.')

    commande = get_object_or_404(Commande, pk=pk)
    if commande.statut == 'PAYEE':
        return JsonResponse({'success': False, 'error': 'Commande déjà payée.'})

    commande.statut = statut
    commande.traiteur = request.user
    commande.save(update_fields=['statut', 'traiteur', 'date_modification'])

    return JsonResponse({'success': True, 'statut': commande.statut})