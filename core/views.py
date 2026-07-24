from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum, Count, Q
from django.utils import timezone

from .decorators import role_required
from .models import Commande, Produit, LigneCommande


# ==========================================
# REDIRECTION INITIALE
# ==========================================

@login_required
def redirect_dashboard(request):
    """Achemine l'utilisateur vers son espace dédié selon son rôle."""
    if request.user.is_superuser or request.user.groups.filter(name='Admin').exists():
        return redirect('admin_dashboard')
    
    groups = request.user.groups.values_list('name', flat=True)
    if 'Serveur' in groups:
        return redirect('serveur_dashboard')
    elif 'Caissier' in groups:
        return redirect('caissier_dashboard')
    
    # Fallback si aucun groupe assigné
    return render(request, 'core/no_role.html')


# ==========================================
# ESPACE ADMINISTRATION
# ==========================================

@login_required
@role_required('Admin')
def admin_dashboard(request):
    today = timezone.now().date()
    now = timezone.now()

    # 1. Récupération des filtres depuis la requête GET
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    serveur_id = request.GET.get('serveur')
    periode = request.GET.get('periode')

    # Gestion des raccourcis temporels
    if periode == 'today':
        date_debut = today
        date_fin = today
    elif periode == 'month':
        date_debut = today.replace(day=1)
        date_fin = today
    elif periode == '7days' or (not date_debut and not date_fin):
        date_debut = today - timedelta(days=6)
        date_fin = today

    # 2. Filtrage dynamique du QuerySet
    commandes = Commande.objects.all()

    if date_debut:
        commandes = commandes.filter(date_creation__date__gte=date_debut)
    if date_fin:
        commandes = commandes.filter(date_creation__date__lte=date_fin)
    if serveur_id:
        commandes = commandes.filter(serveur_id=serveur_id)

    commandes_payees = commandes.filter(statut='PAYEE')

    # 3. Calcul des KPI
    ca_periode = commandes_payees.aggregate(Sum('total_montant'))['total_montant__sum'] or 0
    
    # CA Mois / Année globaux
    ca_mois = Commande.objects.filter(
        statut='PAYEE', 
        date_creation__month=now.month, 
        date_creation__year=now.year
    ).aggregate(Sum('total_montant'))['total_montant__sum'] or 0

    ca_annee = Commande.objects.filter(
        statut='PAYEE', 
        date_creation__year=now.year
    ).aggregate(Sum('total_montant'))['total_montant__sum'] or 0

    kpis = {
        'ca_periode': ca_periode,
        'ca_mois': ca_mois,
        'ca_annee': ca_annee,
        'total_commandes': commandes.count(),
        'en_attente': commandes.filter(statut='EN_ATTENTE').count(),
        'validees': commandes_payees.count(),
        'annulees': commandes.filter(statut='ANNULE').count(),
        'nb_serveurs': User.objects.filter(groups__name='Serveur').count(),
        'nb_caissiers': User.objects.filter(groups__name='Caissier').count(),
    }

    # 4. Top 5 des produits les plus vendus sur la période
    top_produits = LigneCommande.objects.filter(
        commande__in=commandes_payees
    ).values('produit__nom').annotate(
        total_vendu=Sum('quantite')
    ).order_by('-total_vendu')[:5]

    # 5. Top Serveurs
    top_serveurs = User.objects.filter(groups__name='Serveur').annotate(
        nb_commandes=Count('commandes_prises', filter=Q(commandes_prises__in=commandes_payees))
    ).order_by('-nb_commandes')[:5]

    # 6. Données du graphique chronologique
    d_start = datetime.strptime(str(date_debut), '%Y-%m-%d').date() if isinstance(date_debut, str) else date_debut
    d_end = datetime.strptime(str(date_fin), '%Y-%m-%d').date() if isinstance(date_fin, str) else date_fin

    chart_labels = []
    chart_data = []

    current_date = d_start
    while current_date <= d_end:
        chart_labels.append(current_date.strftime('%d/%m'))
        ca_jour = commandes_payees.filter(
            date_creation__date=current_date
        ).aggregate(Sum('total_montant'))['total_montant__sum'] or 0
        chart_data.append(float(ca_jour))
        current_date += timedelta(days=1)

    list_serveurs = User.objects.filter(groups__name='Serveur')

    context = {
        'kpis': kpis,
        'top_produits': top_produits,
        'top_serveurs': top_serveurs,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'list_serveurs': list_serveurs,
        'filters': {
            'date_debut': str(date_debut) if date_debut else '',
            'date_fin': str(date_fin) if date_fin else '',
            'serveur': serveur_id or '',
        }
    }
    
    return render(request, 'admin_custom/dashboard.html', context)


# ==========================================
# ESPACE SERVEUR
# ==========================================

@login_required
@role_required('Serveur')
def serveur_dashboard(request):
    today = timezone.now().date()
    user_commandes = Commande.objects.filter(serveur=request.user)

    stats = {
        'total_commandes': user_commandes.count(),
        'en_attente': user_commandes.filter(statut='EN_ATTENTE').count(),
        'validees': user_commandes.filter(statut='PAYEE').count(),
        'annulees': user_commandes.filter(statut='ANNULE').count(),
        'du_jour': user_commandes.filter(date_creation__date=today).count(),
    }

    commandes_filtrees = user_commandes

    statut = request.GET.get('statut')
    if statut:
        commandes_filtrees = commandes_filtrees.filter(statut=statut)

    periode = request.GET.get('periode', 'today')
    if periode == 'today':
        commandes_filtrees = commandes_filtrees.filter(date_creation__date=today)
    elif periode == 'week':
        start_week = today - timedelta(days=today.weekday())
        commandes_filtrees = commandes_filtrees.filter(date_creation__date__gte=start_week)
    elif periode == 'month':
        commandes_filtrees = commandes_filtrees.filter(date_creation__month=today.month, date_creation__year=today.year)

    commandes_recentes = commandes_filtrees.order_by('-date_creation')[:10]

    context = {
        'stats': stats,
        'commandes_recentes': commandes_recentes,
    }
    return render(request, 'serveur/dashboard.html', context)


@login_required
@role_required('Serveur')
def nouvelle_commande(request):
    """Page de prise de commande interactive pour le serveur."""
    if request.method == 'POST':
        table = request.POST.get('table')
        produits_ids = request.POST.getlist('produits[]')
        quantites = request.POST.getlist('quantites[]')

        if not table or not produits_ids:
            return redirect('nouvelle_commande')

        # 1. Créer la commande initialement à 0
        commande = Commande.objects.create(
            serveur=request.user,
            table=table,
            statut='EN_ATTENTE',
            total_montant=0
        )

        total = 0
        # 2. Ajouter les lignes de commande
        for p_id, qte in zip(produits_ids, quantites):
            qte = int(qte)
            if qte > 0:
                produit = get_object_or_404(Produit, id=p_id)
                LigneCommande.objects.create(
                    commande=commande,
                    produit=produit,
                    quantite=qte,
                    prix_unitaire=produit.prix
                )
                total += produit.prix * qte

        # 3. Mettre à jour le montant total
        commande.total_montant = total
        commande.save()

        return redirect('serveur_dashboard')

    produits = Produit.objects.all()
    return render(request, 'serveur/nouvelle_commande.html', {'produits': produits})


@login_required
@role_required('Serveur')
def serveur_historique(request):
    commandes = Commande.objects.filter(serveur=request.user).order_by('-date_creation')

    statut = request.GET.get('statut')
    if statut:
        commandes = commandes.filter(statut=statut)

    periode = request.GET.get('periode')
    today = timezone.now().date()
    
    if periode == 'today':
        commandes = commandes.filter(date_creation__date=today)
    elif periode == 'week':
        start_week = today - timedelta(days=today.weekday())
        commandes = commandes.filter(date_creation__date__gte=start_week)
    elif periode == 'month':
        commandes = commandes.filter(date_creation__month=today.month, date_creation__year=today.year)
    elif periode == 'custom':
        date_debut = request.GET.get('date_debut')
        date_fin = request.GET.get('date_fin')
        if date_debut and date_fin:
            commandes = commandes.filter(date_creation__date__range=[date_debut, date_fin])

    return render(request, 'serveur/historique.html', {'commandes': commandes})


# ==========================================
# ESPACE CAISSIER
# ==========================================

@login_required
@role_required('Caissier')
def caissier_dashboard(request):
    """Tableau de bord unique du caissier avec stats, filtres et commandes en attente d'encaissement."""
    today = timezone.now().date()
    
    # 1. Filtres GET
    serveur_id = request.GET.get('serveur')
    date_filtre = request.GET.get('date')

    # 2. Requêtes de base
    commandes_a_encaisser = Commande.objects.exclude(statut='PAYEE').order_by('-date_creation')
    commandes_payees = Commande.objects.filter(statut='PAYEE').order_by('-date_modification')

    # 3. Application des filtres
    if serveur_id:
        commandes_a_encaisser = commandes_a_encaisser.filter(serveur_id=serveur_id)
        commandes_payees = commandes_payees.filter(serveur_id=serveur_id)

    if date_filtre:
        commandes_a_encaisser = commandes_a_encaisser.filter(date_creation__date=date_filtre)
        commandes_payees = commandes_payees.filter(date_creation__date=date_filtre)

    # 4. Statistiques Caissier
    commandes_caissier = Commande.objects.filter(caissier=request.user, statut='PAYEE')
    stats = {
        'total_encaissees': commandes_caissier.count(),
        'montant_total': commandes_caissier.aggregate(Sum('total_montant'))['total_montant__sum'] or 0,
        'du_jour': commandes_caissier.filter(date_creation__date=today).count(),
        'du_mois': commandes_caissier.filter(date_creation__month=today.month, date_creation__year=today.year).count(),
    }

    # 5. Liste des serveurs pour le filtre
    serveurs = User.objects.filter(groups__name='Serveur')

    context = {
        'stats': stats,
        'commandes_a_encaisser': commandes_a_encaisser,
        'commandes_payees': commandes_payees[:10],
        'serveurs': serveurs,
    }
    return render(request, 'caissier/caisse.html', context)


@login_required
@role_required('Caissier')
def valider_paiement(request, commande_id):
    """Validation de l'encaissement par le caissier."""
    if request.method == 'POST':
        commande = get_object_or_404(Commande, id=commande_id)
        
        # Validation du règlement
        commande.statut = 'PAYEE'
        commande.caissier = request.user
        commande.save()

        return redirect('caissier_dashboard')


@login_required
@role_required('Caissier')
def caissier_historique(request):
    commandes = Commande.objects.filter(statut='PAYEE').order_by('-date_modification')

    q = request.GET.get('q')
    if q:
        commandes = commandes.filter(Q(id__icontains=q) | Q(table__icontains=q))

    periode = request.GET.get('periode')
    today = timezone.now().date()
    if periode == 'today':
        commandes = commandes.filter(date_modification__date=today)
    elif periode == 'month':
        commandes = commandes.filter(date_modification__month=today.month, date_modification__year=today.year)

    return render(request, 'caissier/historique.html', {'commandes': commandes})


@login_required
@role_required('Caissier')
def imprimer_recu(request, commande_id):
    """Vue formatée sans header/footer pour impression directe du ticket de caisse."""
    commande = get_object_or_404(Commande, id=commande_id)
    return render(request, 'caissier/recu_print.html', {'commande': commande})