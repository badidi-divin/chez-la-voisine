import os
import django

# Configuration du projet Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restofast_project.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Récupération des identifiants depuis les variables d'environnement
username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin')

if not User.objects.filter(username=username).exists():
    print(f"Création du superutilisateur : {username}")
    User.objects.create_superuser(username=username, email=email, password=password)
    print("Superutilisateur créé avec succès !")
else:
    print(f"Le superutilisateur '{username}' existe déjà.")
