import os
import django

# Configuration du projet Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restofast_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()

# =====================================================
# 1. NETTOYAGE ET RECRÉATION DES GROUPES
# =====================================================

print("Suppression de tous les anciens groupes...")
Group.objects.all().delete()

print("Création des nouveaux groupes officiels...")
GROUPES_OFFICIELS = ['Serveur', 'Caissier']

for nom_groupe in GROUPES_OFFICIELS:
    Group.objects.create(name=nom_groupe)
    print(f" -> Groupe '{nom_groupe}' créé avec succès !")


# =====================================================
# 2. CRÉATION DU SUPERUTILISATEUR (ADMIN)
# =====================================================

username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')

if not User.objects.filter(username=username).exists():
    print(f"Création du superutilisateur : {username}")
    User.objects.create_superuser(username=username, email=email, password=password)
    print("Superutilisateur créé avec succès !")
else:
    print(f"Le superutilisateur '{username}' existe déjà.")
