"""
====================================================================================================
SISTEMA DE REPOSITORIO ACADÉMICO INSTITUCIONAL (FCA - UABC)
Módulo: Pagina/apps.py
Descripción: Configuración de la aplicación principal 'Pagina' dentro del ecosistema Django.
Autor: Facultad de Contaduría y Administración - Campus Tijuana
====================================================================================================
Establece los metadatos de la aplicación institucional, tipos de clave primaria predeterminados
y la inicialización de manejadores o señales cuando la aplicación es cargada por el framework.
"""

from django.apps import AppConfig


class PaginaConfig(AppConfig):
    """
    Configuración de la aplicación central 'Pagina'.
    Define el tipo de campo auto-incremental a BigAutoField (64 bits) para soportar millones
    de registros en artículos, descargas, métricas y bitácoras de auditoría institucional.
    """
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Pagina'
    verbose_name = 'Repositorio Institucional FCA UABC'
