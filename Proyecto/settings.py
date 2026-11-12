"""
====================================================================================================
UNIVERSIDAD AUTÓNOMA DE BAJA CALIFORNIA (UABC)
Facultad de Contaduría y Administración (FCA) - Campus Tijuana
Plataforma: Repositorio Académico Institucional de la FCA
Módulo: Proyecto / Configuración Global del Sistema (settings.py)
====================================================================================================

DESCRIPCIÓN GENERAL:
    Archivo central de configuración de Django para la plataforma del Repositorio FCA.
    Establece las directivas de seguridad criptográfica, conectividad a motores de base de datos
    (PostgreSQL / MySQL / SQLite), gestión de archivos estáticos y multimedia, validación
    institucional de contraseñas, zona horaria oficial (America/Tijuana) y servicios
    transaccionales de correo electrónico institucional (SMTP/Gmail).

ARQUITECTURA DE DESPLIEGUE:
    - Diseñado para operar de forma transparente en entornos de Desarrollo Local (MySQL / SQLite)
      y Producción Institucional de Alta Concurrencia (Gunicorn + Nginx + PostgreSQL / MySQL).
    - Soporte nativo para configuración desacoplada mediante variables de entorno (.env).
====================================================================================================
"""

import os
from pathlib import Path
import dj_database_url

# ==================================================================================================
# 1. RUTAS BASE Y CARGA DE VARIABLES DE ENTORNO
# ==================================================================================================
# Directorio raíz del proyecto (Repositorio-FCA/)
BASE_DIR = Path(__file__).resolve().parent.parent

# Carga automática de variables de entorno desde archivo local .env (si existe)
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


# ==================================================================================================
# 2. SEGURIDAD, CLAVES CRIPTOGRÁFICAS Y ANFITRIONES PERMITIDOS
# ==================================================================================================
# Clave criptográfica para firmas de sesión y protección de cookies (sobreescribir en producción)
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-bvn=ds@r6hrv5=avy*8j@j$w_eb^!rh3biad9r4wd!qm9ui!hn'
)

# Modo Depuración: En producción debe definirse DJANGO_DEBUG=False
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 't')

# Anfitriones y dominios autorizados para atender peticiones HTTP
ALLOWED_HOSTS = ['*']


# ==================================================================================================
# 3. APLICACIONES INSTALADAS (INSTALLED_APPS)
# ==================================================================================================
INSTALLED_APPS = [
    # Aplicaciones nativas del framework Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Aplicación principal del Repositorio Académico FCA
    'Pagina.apps.PaginaConfig',
]


# ==================================================================================================
# 4. CAPA DE MIDDLEWARE (SEGURIDAD Y SESIONES)
# ==================================================================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',         # Entrega optimizada de archivos estáticos
    'django.contrib.sessions.middleware.SessionMiddleware', # Gestión de sesiones de usuario en cookies
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',             # Protección contra falsificación de peticiones
    'django.contrib.auth.middleware.AuthenticationMiddleware', # Vinculación de request.user
    'django.contrib.messages.middleware.MessageMiddleware',    # Sistema de mensajes flash (éxito/error)
    'django.middleware.clickjacking.XFrameOptionsMiddleware', # Prevención de clickjacking en iframes
]

# Enrutador maestro de URLs
ROOT_URLCONF = 'Proyecto.urls'


# ==================================================================================================
# 5. MOTOR DE PLANTILLAS Y PROCESADORES DE CONTEXTO
# ==================================================================================================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Directorio global de plantillas HTML
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                # Procesador institucional: inyecta notificaciones, solicitudes y configuración en todas las vistas
                'Pagina.context_processors.notificaciones_institucionales',
            ],
        },
    },
]

# Servidor de aplicación WSGI
WSGI_APPLICATION = 'Proyecto.wsgi.application'


# ==================================================================================================
# 6. MOTOR DE BASE DE DATOS AGNÓSTICO (POSTGRESQL / MYSQL / SQLITE)
# ==================================================================================================
# El sistema utiliza la URL de base de datos estándar (DATABASE_URL) para adaptarse automáticamente:
# - PostgreSQL institucional: postgres://usuario:password@host:5432/nombre_bd
# - MySQL / MariaDB institucional: mysql://usuario:password@host:3306/nombre_bd
# - SQLite portátil: para entornos de pruebas locales o aislamiento rápido
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL)
    }
elif os.environ.get('RENDER') or os.environ.get('USE_SQLITE'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    # Entorno local por defecto (MySQL de desarrollo institucional)
    DATABASES = {
        'default': dj_database_url.config(
            default='mysql://root:ElYaelexD22@localhost:3306/uabc'
        )
    }

# Ajustes de codificación para MySQL / MariaDB (soporte de acentos, eñes y caracteres universitarios)
if DATABASES['default'].get('ENGINE') == 'django.db.backends.mysql':
    DATABASES['default'].setdefault('OPTIONS', {})
    DATABASES['default']['OPTIONS']['charset'] = 'utf8mb4'
    DATABASES['default']['OPTIONS']['init_command'] = (
        "SET sql_mode='STRICT_TRANS_TABLES', names 'utf8mb4' COLLATE 'utf8mb4_unicode_ci'"
    )


# ==================================================================================================
# 7. VALIDACIÓN DE CONTRASEÑAS INSTITUCIONALES
# ==================================================================================================
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ==================================================================================================
# 8. INTERNACIONALIZACIÓN Y ZONA HORARIA
# ==================================================================================================
LANGUAGE_CODE = 'es-mx'                  # Español México institucional
TIME_ZONE = 'America/Tijuana'            # Zona horaria oficial del Campus Tijuana (PST / PDT)
USE_I18N = True                          # Habilitar internacionalización
USE_TZ = True                            # Almacenamiento UTC con conversión automática a hora local


# ==================================================================================================
# 9. ARCHIVOS ESTÁTICOS Y MULTIMEDIA (ACERVO DIGITAL)
# ==================================================================================================
# Archivos estáticos del sistema (CSS, JavaScript, logos institucionales)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Archivos multimedia subidos por los docentes (PDFs de tesis, fotos de claustro, constancias)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Tipo de clave primaria por defecto
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Ruta de redirección para usuarios no autenticados
LOGIN_URL = '/login/'


# ==================================================================================================
# 10. AUTENTICACIÓN INSTITUCIONAL DUAL (CORREO O USERNAME)
# ==================================================================================================
AUTHENTICATION_BACKENDS = [
    # Backend personalizado: permite a los docentes ingresar con su correo UABC o con su username
    'Pagina.backends.EmailOrUsernameModelBackend',
    'django.contrib.auth.backends.ModelBackend',
]


# ==================================================================================================
# 11. MOTOR DE NOTIFICACIONES POR CORREO ELECTRÓNICO (SMTP / GMAIL)
# ==================================================================================================
EMAIL_BACKEND = os.getenv('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))

# Soporte automático para cifrado SSL (puerto 465) o TLS (puerto 587)
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL', 'False').lower() in ('true', '1', 't')
if EMAIL_USE_SSL:
    EMAIL_USE_TLS = False
else:
    EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')

EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL',
    f'Repositorio FCA UABC <{EMAIL_HOST_USER}>' if EMAIL_HOST_USER else 'Repositorio FCA UABC <notificaciones.fca.uabc@gmail.com>'
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Timeout corto de 4 segundos para evitar que los procesos de Gunicorn se congelen si el puerto SMTP está cerrado
EMAIL_TIMEOUT = 4
