from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone


class Categorie(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"

    def __str__(self):
        return self.nom


class Produit(models.Model):
    categorie = models.ForeignKey(Categorie, on_delete=models.CASCADE, related_name="produits")
    nom = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True, null=True)
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    stock_actuel = models.PositiveIntegerField(default=0)
    stock_alerte = models.PositiveIntegerField(default=5, help_text="Seuil de stock critique")
    disponible = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Produit"
        verbose_name_plural = "Produits"

    def clean(self):
        if self.stock_actuel <= 0:
            self.disponible = False

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def en_alerte(self):
        return self.stock_actuel <= self.stock_alerte

    def reserved_by_others(self, session_key=None):
        reservations = self.stock_reservations.all()
        if session_key:
            reservations = reservations.exclude(session_key=session_key)
        expiration = timezone.now() - timedelta(minutes=15)
        reservations = reservations.filter(updated_at__gte=expiration)
        return reservations.aggregate(total=models.Sum('quantite'))['total'] or 0

    def available_stock_for_session(self, session_key=None):
        return max(self.stock_actuel - self.reserved_by_others(session_key=session_key), 0)

    def __str__(self):
        return f"{self.nom} ({self.stock_actuel} en stock)"


class ReservationStock(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='stock_reservations')
    session_key = models.CharField(max_length=40, db_index=True)
    serveur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    quantite = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('produit', 'session_key')
        verbose_name = "Réservation de stock"
        verbose_name_plural = "Réservations de stock"

    def __str__(self):
        return f"Réservation {self.quantite}x {self.produit.nom} ({self.session_key})"


class Commande(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_PREPARATION', 'En préparation'),
        ('PRET', 'Prêt'),
        ('PAYEE', 'Payée'),
        ('ANNULE', 'Annulée'),
    ]

    serveur = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        limit_choices_to={'groups__name': 'Serveur'},
        related_name='commandes_prises'
    )
    traiteur = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'groups__name': 'Traiteur'},
        related_name='commandes_preparees'
    )
    caissier = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'groups__name': 'Caissier'},
        related_name='commandes_encaissees'
    )
    table = models.CharField(max_length=50)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    total_montant = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Commande"
        verbose_name_plural = "Commandes"
        ordering = ['-date_creation']

    @property
    def total_commande(self):
        return sum(ligne.sous_total for ligne in self.lignes.all())

    def update_total(self):
        self.total_montant = self.total_commande
        self.save(update_fields=['total_montant'])

    def __str__(self):
        return f"Commande #{self.id} - Table {self.table} - {self.get_statut_display()}"


class LigneCommande(models.Model):
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT)
    quantite = models.PositiveIntegerField(default=1)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    est_pret = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Ligne de commande"
        verbose_name_plural = "Lignes de commande"

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire

    def clean(self):
        if self.quantite > self.produit.stock_actuel:
            raise ValidationError(
                f"Stock insuffisant pour {self.produit.nom}. Stock actuel : {self.produit.stock_actuel}."
            )

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            self.clean()
            self.prix_unitaire = self.produit.prix
            self.produit.stock_actuel -= self.quantite
            self.produit.save(update_fields=['stock_actuel', 'disponible'])

        super().save(*args, **kwargs)
        self.commande.total_montant = self.commande.total_commande
        self.commande.save(update_fields=['total_montant'])

    def __str__(self):
        return f"{self.quantite}x {self.produit.nom} (Commande #{self.commande.id})"
