"""
Django settings for restofast_project project.
"""

import os
from pathlib import Path
import dj_database_url

# Chemin principal du projet
BASE_DIR = Path(__file__).resolve().parent.parent

# Détecte si le projet s'exécute sur Render
ON_RENDER = 'RENDER' in os.environ


# =====================================================
# SECURITY SETTINGS
# =====================================================

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-bg*mq+qa*+_7qe3c!fvjly4&++ns+=02_4#9i$#3amn!=-j%tz')

DEBUG = os.environ.get('DEBUG', 'True' if not ON_RENDER else 'False') == 'True'

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '.onrender.com']
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = [
    'https://*.onrender.com',
]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_EXTERNAL_HOSTNAME}')


# =====================================================
# APPLICATIONS
# =====================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'core',
]


# =====================================================
# MIDDLEWARE
# =====================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # WhiteNoise juste après SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# =====================================================
# URL / WSGI
# =====================================================

ROOT_URLCONF = 'restofast_project.urls'
WSGI_APPLICATION = 'restofast_project.wsgi.application'


# =====================================================
# TEMPLATES
# =====================================================

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]


# =====================================================
# DATABASE CONFIGURATION
# =====================================================

DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'universite_db',
            'USER': 'postgres',
            'PASSWORD': '0000',
            'HOST': 'localhost',
            'PORT': '5432',
        }
    }


# =====================================================
# VALIDATION MOT DE PASSE & INTERNATIONALISATION
# =====================================================

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'Africa/Kinshasa'
USE_I18N = True
USE_TZ = True


# =====================================================
# STATIC FILES
# =====================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

if ON_RENDER:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }


# =====================================================
# AUTHENTIFICATION
# =====================================================

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'redirect_dashboard'
