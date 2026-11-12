"""
====================================================================================================
SISTEMA DE REPOSITORIO ACADÉMICO INSTITUCIONAL (FCA - UABC)
Módulo: Proyecto/urls.py
Descripción: Enrutador Maestro de URLs y Despachador Global de Rutas del Sistema.
Autor: Facultad de Contaduría y Administración - Campus Tijuana
====================================================================================================
Este archivo constituye la tabla de enrutamiento raíz (ROOT_URLCONF) de todo el sistema.
Su responsabilidad es recibir cada solicitud HTTP entrante, evaluar la URI solicitada
y derivar el control al subsistema correspondiente:

1. /admin/ : Panel de Control y Administración Nativo de Django (superusuarios y auditoría técnica).
2. /       : Módulo Principal de la Aplicación Institucional (Pagina.urls), que gestiona el acervo,
             claustro docente, autenticación dual, moderación y soporte técnico.
3. /media/ : Despacho y entrega segura de archivos multimedia persistentes (tesis en PDF,
             constancias, portadas y fotografías del claustro de profesores).
====================================================================================================
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

# ==================================================================================================
# DEFINICIÓN DE RUTAS MAESTRAS (URLPATTERNS)
# ==================================================================================================
urlpatterns = [
    # ----------------------------------------------------------------------------------------------
    # 1. PANEL DE ADMINISTRACIÓN DE BAJO NIVEL (DJANGO ADMIN)
    # ----------------------------------------------------------------------------------------------
    # Proporciona acceso directo al modelo relacional de datos para mantenimiento de emergencia,
    # configuración de grupos de permisos y gestión de superusuarios por parte del equipo de TI.
    path('admin/', admin.site.urls),

    # ----------------------------------------------------------------------------------------------
    # 2. SISTEMA PRINCIPAL DEL REPOSITORIO INSTITUCIONAL (APP: PAGINA)
    # ----------------------------------------------------------------------------------------------
    # Incluye el árbol completo de rutas operativas: catálogo público, búsqueda multifiltro,
    # panel de usuario y claustro docente, flujo de carga y coautorías, sistema de moderación,
    # auditoría, copias de seguridad y mesa de ayuda / simulador de soporte.
    path("", include("Pagina.urls")),

    # ----------------------------------------------------------------------------------------------
    # 3. CONTROLADOR DE ARCHIVOS MULTIMEDIA PERSISTENTES (MEDIA FILES)
    # ----------------------------------------------------------------------------------------------
    # Permite el acceso directo a los archivos cargados por docentes y alumnos (artículos en PDF,
    # portadas de libros, tesis de posgrado y avatares del claustro docente).
    # En desarrollo y servidores WSGI unificados, se despacha mediante la vista estática segura de Django.
    # En servidores de producción con Nginx, esta ruta puede ser interceptada a nivel de proxy inverso
    # para aceleración por caché física y descarga de alto rendimiento sin saturar hilos de Python.
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
