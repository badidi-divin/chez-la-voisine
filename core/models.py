from django.db import models, transaction
from django.db.models import F
from django.contrib.auth.models import User


class Categorie(models.Model):
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nom


class Produit(models.Model):
    nom = models.CharField(max_length=150)
    categorie = models.ForeignKey(Categorie, on_delete=models.CASCADE, related_name='produits')
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    stock_actuel = models.IntegerField(default=0)
    stock_alerte = models.IntegerField(default=5)
    disponible = models.BooleanField(default=True)

    def __str__(self):
        return self.nom

    @property
    def en_alerte(self):
        return self.stock_actuel <= self.stock_alerte


class ReservationStock(models.Model):
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    quantite = models.PositiveIntegerField(default=1)
    session_key = models.CharField(max_length=100)
    serveur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Réservation {self.quantite}x {self.produit.nom}"


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

    def __str__(self):
        return f"Commande #{self.id} - Table {self.table}"

    def update_total(self):
        total = sum(item.sous_total for item in self.lignes.all())
        self.total_montant = total
        self.save()

    def annuler_commande(self):
        if self.statut != 'ANNULE':
            with transaction.atomic():
                for ligne in self.lignes.all():
                    Produit.objects.filter(id=ligne.produit_id).update(
                        stock_actuel=F('stock_actuel') + ligne.quantite
                    )
                self.statut = 'ANNULE'
                self.save()


class LigneCommande(models.Model):
    commande = models.ForeignKey(Commande, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT)
    quantite = models.PositiveIntegerField(default=1)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    est_pret = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.quantite}x {self.produit.nom}"

    @property
    def sous_total(self):
        return self.quantite * self.prix_unitaire

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new:
            self.prix_unitaire = self.produit.prix
            with transaction.atomic():
                Produit.objects.filter(id=self.produit_id).update(
                    stock_actuel=F('stock_actuel') - self.quantite
                )
        super().save(*args, **kwargs)
        self.commande.update_total()