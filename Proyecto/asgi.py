"""
====================================================================================================
SISTEMA DE REPOSITORIO ACADÉMICO INSTITUCIONAL (FCA - UABC)
Módulo: Proyecto/asgi.py
Descripción: Punto de Entrada de la Aplicación bajo el Estándar ASGI (Asynchronous Server Gateway Interface).
Autor: Facultad de Contaduría y Administración - Campus Tijuana
====================================================================================================
Este archivo implementa la especificación ASGI (Asynchronous Server Gateway Interface), la cual
extiende el modelo tradicional WSGI para dar soporte a protocolos concurrentes y asíncronos en Python.

Expone el objeto invocable (callable) `application` para servidores ASGI de alto rendimiento
(tales como Uvicorn, Daphne o Hypercorn).

Aplicabilidad dentro de la infraestructura institucional:
- Gestión asíncrona de solicitudes HTTP no bloqueantes.
- Soporte para WebSockets en tiempo real (notificaciones push instantáneas, indicadores de presencia
  del claustro docente o chats de soporte en vivo sin sobrecargar la base de datos con peticiones constantes).
- Manejo de conexiones persistentes (Server-Sent Events y streaming de descargas masivas de acervos).

En caso de utilizar workers asíncronos en producción, el servicio se levanta invocando:
    uvicorn Proyecto.asgi:application --host 127.0.0.1 --port 8000 --workers 4
====================================================================================================
"""

import os

from django.core.asgi import get_asgi_application

# Establece el módulo de configuración de Django predeterminado para el proceso ASGI
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Proyecto.settings')

# Instancia ejecutable ASGI capaz de gestionar eventos síncronos y asíncronos concurrentes
application = get_asgi_application()
