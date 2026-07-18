import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'restofast_project.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Modifiez vos identifiants ici
username = 'admin'
email = 'admin@example.com'
password = '12345'

if not User.objects.filter(username=username).exists():
    print(f"Création du superutilisateur {username}...")
    User.objects.create_superuser(username=username, email=email, password=password)
    print("Superutilisateur créé avec succès !")
else:
    print(f"Le superutilisateur {username} existe déjà.")