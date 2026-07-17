from django.contrib import admin
from django.utils.html import format_html
from .models import Categorie, Produit, Commande, LigneCommande


# Personnalisation des titres de l'interface d'administration
admin.site.site_header = "Espace La Voisine Admin"                    # Titre dans la barre supérieure bleue
admin.site.site_title = "Espace La Voisine Admin"                 # Titre de l'onglet du navigateur
admin.site.index_title = "Gestion du Restaurant"          # Sous-titre sur la page d'accueil de l'admin


# Helper de formatage pour les prix en Franc Congolais (FC)
def formater_fc(valeur):
    if valeur is None:
        return "0 FC"
    # Formate le nombre avec séparateur de milliers (ex: 15 000 FC)
    return f"{int(valeur):,}".replace(",", " ") + " FC"


# --- 1. CONFIGURATION DES PRODUITS ---

@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    # 'prix' reste dans list_editable pour être modifié, mais on affiche 'prix_affiche' pour la lisibilité
    list_display = ('nom', 'categorie', 'prix_affiche', 'prix', 'stock_actuel', 'statut_stock', 'disponible')
    list_filter = ('categorie', 'disponible')
    search_fields = ('nom',)
    list_editable = ('prix', 'stock_actuel', 'disponible')  # Permet de modifier rapidement depuis la liste

    # Affichage propre du prix dans la liste
    def prix_affiche(self, obj):
        return formater_fc(obj.prix)
    prix_affiche.short_description = "Prix de vente"
    prix_affiche.admin_order_field = "prix"

    # Indicateur visuel pour le gérant (Aide à la décision)
    def statut_stock(self, obj):
        if obj.stock_actuel == 0:
            return format_html('<span style="color: red; font-weight: bold;">🔴 Rupture de stock</span>', "")
        elif obj.en_alerte:
            return format_html('<span style="color: orange; font-weight: bold;">⚠️ Stock Critique ({})</span>', obj.stock_actuel)
        return format_html('<span style="color: green;">🟢 En Stock</span>', "")
    
    statut_stock.short_description = "État du Stock"


# --- 2. CONFIGURATION DES COMMANDES (EDITION EN CASCADE) ---

class LigneCommandeInline(admin.TabularInline):
    """Permet d'ajouter/modifier des produits directement dans la commande"""
    model = LigneCommande
    extra = 1 # Nombre de lignes vides affichées par défaut
    readonly_fields = ('prix_unitaire_affiche', 'sous_total_affiche')
    fields = ('produit', 'quantite', 'prix_unitaire_affiche', 'sous_total_affiche')

    # Affichage du prix unitaire en FC
    def prix_unitaire_affiche(self, obj):
        if obj.id:
            return formater_fc(obj.prix_unitaire)
        return "-"
    prix_unitaire_affiche.short_description = "Prix Unitaire"

    # Affichage du sous-total de la ligne en FC
    def sous_total_affiche(self, obj):
        if obj.id:
            return formater_fc(obj.sous_total)
        return "-"
    sous_total_affiche.short_description = "Sous-total"


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    # Liste globale des commandes pour le gérant et le caissier
    list_display = ('id', 'table', 'serveur', 'statut_badge', 'total_calcule', 'date_creation', 'caissier')
    list_filter = ('statut', 'date_creation', 'serveur')
    search_fields = ('id', 'table')
    
    # Intégration des lignes de commande dans la fiche de commande
    inlines = [LigneCommandeInline]

    # Badges de couleur pour suivre l'état du workflow en un coup d'œil
    def statut_badge(self, obj):
        colors = {
            'EN_ATTENTE': '#ffc107',      # Jaune
            'EN_PREPARATION': '#17a2b8',  # Bleu info
            'SERVI': '#28a745',           # Vert
            'PAYE': '#6c757d',            # Gris (clôturé)
            'ANNULE': '#dc3545',          # Rouge
        }
        color = colors.get(obj.statut, '#000')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            color,
            obj.get_statut_display()
        )
    
    statut_badge.short_description = "Statut"

    # Affichage du total de la commande globale en FC
    def total_calcule(self, obj):
        return formater_fc(obj.total_commande)
    total_calcule.short_description = "Montant Total"
    total_calcule.admin_order_field = "total_commande"