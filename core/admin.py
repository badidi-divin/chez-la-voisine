from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Categorie, Produit, ReservationStock, Commande, LigneCommande


# Personnalisation des titres de l'interface d'administration
admin.site.site_header = "Espace La Voisine Admin"
admin.site.site_title = "Espace La Voisine Admin"
admin.site.index_title = "Gestion du Restaurant"


# Helper de formatage pour les prix en Franc Congolais (FC)
def formater_fc(valeur):
    if valeur is None:
        return "0 FC"
    return f"{int(valeur):,}".replace(",", " ") + " FC"


# --- 1. CATÉGORIES ET PRODUITS ---

@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = (
        'nom', 
        'categorie', 
        'prix_affiche', 
        'prix', 
        'stock_actuel', 
        'stock_alerte', 
        'statut_stock', 
        'disponible'
    )
    list_filter = ('categorie', 'disponible')
    search_fields = ('nom',)
    list_editable = ('prix', 'stock_actuel', 'disponible')

    def prix_affiche(self, obj):
        return formater_fc(obj.prix)
    prix_affiche.short_description = "Prix de vente"
    prix_affiche.admin_order_field = "prix"

    def statut_stock(self, obj):
        if obj.stock_actuel == 0:
            return mark_safe('<span style="color: red; font-weight: bold;">🔴 Rupture</span>')
        elif obj.en_alerte:
            return format_html(
                '<span style="color: orange; font-weight: bold;">⚠️ Critique ({stock})</span>', 
                stock=obj.stock_actuel
            )
        
        return mark_safe('<span style="color: green;">🟢 Disponible</span>')
    
    statut_stock.short_description = "État Stock"


# --- 2. RÉSERVATIONS DE STOCK (PANIERS TEMPORAIRES) ---

@admin.register(ReservationStock)
class ReservationStockAdmin(admin.ModelAdmin):
    list_display = ('produit', 'quantite', 'session_key', 'serveur', 'created_at', 'updated_at')
    list_filter = ('created_at', 'serveur')
    search_fields = ('session_key', 'produit__nom')
    readonly_fields = ('created_at', 'updated_at')


# --- 3. COMMANDES ET LIGNES DE COMMANDE ---

class LigneCommandeInline(admin.TabularInline):
    model = LigneCommande
    extra = 1
    readonly_fields = ('prix_unitaire_affiche', 'sous_total_affiche')
    fields = ('produit', 'quantite', 'prix_unitaire', 'prix_unitaire_affiche', 'sous_total_affiche', 'est_pret')

    def prix_unitaire_affiche(self, obj):
        return formater_fc(obj.prix_unitaire) if obj.id else "-"
    prix_unitaire_affiche.short_description = "Prix Unitaire (FC)"

    def sous_total_affiche(self, obj):
        return formater_fc(obj.sous_total) if obj.id else "-"
    sous_total_affiche.short_description = "Sous-total (FC)"


@admin.register(Commande)
class CommandeAdmin(admin.ModelAdmin):
    list_display = ('id', 'table', 'serveur', 'caissier', 'statut_badge', 'montant_total_display', 'date_creation')
    list_filter = ('statut', 'date_creation', 'serveur', 'caissier')
    search_fields = ('id', 'table')
    inlines = [LigneCommandeInline]
    readonly_fields = ('total_montant', 'date_creation', 'date_modification')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('serveur', 'caissier')

    def statut_badge(self, obj):
        colors = {
            'EN_ATTENTE': '#ffc107',     # Jaune
            'EN_PREPARATION': '#17a2b8', # Bleu info
            'PRET': '#fd7e14',           # Orange
            'PAYEE': '#28a745',          # Vert
            'ANNULE': '#dc3545',         # Rouge
        }
        color = colors.get(obj.statut, '#6c757d')
        return format_html(
            '<span style="background-color: {color}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;">{statut}</span>',
            color=color,
            statut=obj.get_statut_display()
        )
    statut_badge.short_description = "Statut"
    statut_badge.admin_order_field = "statut"

    def montant_total_display(self, obj):
        return formater_fc(obj.total_montant)
    montant_total_display.short_description = "Montant Total"
    montant_total_display.admin_order_field = "total_montant"