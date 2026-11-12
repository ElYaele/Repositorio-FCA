"""
====================================================================================================
SISTEMA DE REPOSITORIO ACADÉMICO INSTITUCIONAL (FCA - UABC)
Módulo: Proyecto/wsgi.py
Descripción: Punto de Entrada de la Aplicación bajo el Estándar WSGI (Web Server Gateway Interface).
Autor: Facultad de Contaduría y Administración - Campus Tijuana
====================================================================================================
Este archivo implementa la especificación PEP 3333 (Python Web Server Gateway Interface v1.0.1).
Expone el objeto invocable (callable) `application` que actúa como interfaz estandarizada entre:

1. Los servidores web de producción orientados a procesos/hilos (Gunicorn, uWSGI o mod_wsgi).
2. El servidor proxy inverso perimetral (Nginx / Apache HTTP Server).
3. El núcleo de ejecución y ciclo de vida de peticiones/respuestas del framework Django.

En el despliegue del servidor institucional (Ubuntu Server / Rocky Linux), este archivo es invocado
por el daemon Gunicorn mediante el comando:
    gunicorn Proyecto.wsgi:application --workers 4 --threads 4 --bind 127.0.0.1:8000
====================================================================================================
"""

import os

from django.core.wsgi import get_wsgi_application

# Establece el módulo de configuración de Django predeterminado para el proceso WSGI
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Proyecto.settings')

# Instancia ejecutable WSGI que atiende las peticiones HTTP entrantes y despacha las respuestas
application = get_wsgi_application()
