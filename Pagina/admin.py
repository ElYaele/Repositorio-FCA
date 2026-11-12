"""
====================================================================================================
SISTEMA DE REPOSITORIO ACADÉMICO INSTITUCIONAL (FCA - UABC)
Módulo: Pagina/admin.py
Descripción: Configuración del Panel Administrativo de Django y Políticas de Auditoría Inmutable.
Autor: Facultad de Contaduría y Administración - Campus Tijuana
====================================================================================================
Este archivo personaliza la interfaz nativa del Django Admin (`/admin/`):
1. Restricción de Acceso de Máxima Seguridad: Se anula el acceso estándar y se restringe estrictamente
   al Superadministrador Principal del sistema (`es_superusuario_principal`). Ningún otro usuario
   o administrador secundario puede autenticarse en esta interfaz perimetral.
2. Bitácora de Auditoría Inmutable (`RegistroAuditoriaAdmin`): El modelo de auditoría forense está blindado
   contra cualquier intento de inserción manual, modificación de registros o eliminación física de trazas.
   Todos los campos se presentan estrictamente como de solo lectura (Read-Only).
3. Administración del Acervo y Catálogos: Configura filtros de búsqueda, optimización horizontal para autores
   múltiples y ordenamiento cronológico para artículos, autores, claustro y universidades.
====================================================================================================
"""

from django.contrib import admin
from .models import (
    Articulo, Entidad, Area, TipoContenido, Autor, MensajeCumpleanos,
    Nombramiento, EnlaceProfesional, RegistroAuditoria, Universidad
)
from .views import es_superusuario_principal


# ==================================================================================================
# 1. POLÍTICA DE SEGURIDAD PERIMETRAL: RESTRICCIÓN EXCLUSIVA AL SUPERADMINISTRADOR PRINCIPAL
# ==================================================================================================
original_admin_has_permission = admin.site.has_permission

def admin_site_exclusivo_superadmin_principal(request):
    """
    Evalúa si la solicitud proviene del Superadministrador Principal institucional.
    Bloquea a usuarios estándar, docentes, moderadores y superusuarios secundarios.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_active or not user.is_superuser:
        return False
    return es_superusuario_principal(user)

# Intercepta el validador nativo de Django Admin
admin.site.has_permission = admin_site_exclusivo_superadmin_principal


# ==================================================================================================
# 2. ADMINISTRACIÓN DEL ACERVO ACADÉMICO (ARTÍCULOS Y TESIS)
# ==================================================================================================
@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    """
    Panel administrativo para el catálogo de obras académicas, tesis y artículos.
    Permite la asignación masiva y asociativa de autores mediante el widget horizontal de selección.
    """
    filter_horizontal = ('autor',)  # Selector dual de autores
    list_display = ('titulo', 'estado', 'tipo_contenido', 'año_produccion', 'entidad', 'subido_por', 'created_at')
    search_fields = ('titulo', 'descripcion', 'autor__nombre')
    list_filter = ('estado', 'tipo_contenido', 'entidad', 'area', 'año_produccion')
    ordering = ('-created_at',)


# ==================================================================================================
# 3. ADMINISTRACIÓN DE IDENTIDADES ACADÉMICAS Y CLAUSTRO (AUTORES)
# ==================================================================================================
@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    """
    Panel administrativo para docentes, investigadores y autores externos.
    """
    list_display = ('nombre', 'correo', 'numero_empleado', 'institucion_origen', 'es_profesor', 'estado_semblanza')
    search_fields = ('nombre', 'correo', 'numero_empleado', 'institucion_origen')
    list_filter = ('es_profesor', 'es_externo', 'estado_semblanza', 'genero')


# ==================================================================================================
# 4. ADMINISTRACIÓN DE UNIVERSIDADES EN CONVENIO
# ==================================================================================================
@admin.register(Universidad)
class UniversidadAdmin(admin.ModelAdmin):
    """
    Catálogo institucional de universidades e institutos tecnológicos externos.
    """
    list_display = ('nombre', 'siglas')
    search_fields = ('nombre', 'siglas')


# ==================================================================================================
# 5. BITÁCORA FORENSE DE AUDITORÍA (INMUTABLE Y PROTEGIDA)
# ==================================================================================================
@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    """
    Panel de auditoría forense institucional.
    Por directriz de seguridad informática y control interno universitario, este modelo
    es completamente inmutable: no se pueden agregar registros manuales, no se pueden modificar
    y no se pueden eliminar trazas existentes.
    """
    list_display = ('accion', 'admin_usuario', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('accion', 'detalle')
    ordering = ('-created_at',)
    actions = None  # Deshabilita acciones en masa (ej. "Eliminar registros seleccionados")

    def has_add_permission(self, request):
        """Impide la creación de registros de auditoría desde el panel; solo el código del sistema los genera."""
        return False

    def has_change_permission(self, request, obj=None):
        """Garantiza la inmutabilidad: ningún registro de auditoría puede ser editado."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Protección contra borrado de evidencias: ningún registro puede ser eliminado."""
        return False

    def get_readonly_fields(self, request, obj=None):
        """Convierte todos los campos en estrictamente de solo lectura."""
        return [f.name for f in self.model._meta.fields]


# ==================================================================================================
# 6. MÓDULOS DE INTERACCIÓN, NOMBRAMIENTOS Y ENLACES DOCENTES
# ==================================================================================================
@admin.register(MensajeCumpleanos)
class MensajeCumpleanosAdmin(admin.ModelAdmin):
    """Registro de felicitaciones y poemas institucionales entre miembros del claustro."""
    list_display = ('para_docente', 'de_usuario', 'fecha_envio')
    list_filter = ('fecha_envio',)
    search_fields = ('mensaje',)


@admin.register(Nombramiento)
class NombramientoAdmin(admin.ModelAdmin):
    """Cargos honoríficos, coordinaciones y distinciones académicas de los docentes."""
    list_display = ('autor', 'rol')
    list_filter = ('rol',)


@admin.register(EnlaceProfesional)
class EnlaceProfesionalAdmin(admin.ModelAdmin):
    """Perfiles profesionales externos (ORCID, ResearchGate, Google Scholar, LinkedIn)."""
    list_display = ('autor', 'plataforma', 'url')
    search_fields = ('plataforma', 'url')


# ==================================================================================================
# 7. CATÁLOGOS TAXONÓMICOS DEL REPOSITORIO
# ==================================================================================================
@admin.register(Entidad)
class EntidadAdmin(admin.ModelAdmin):
    """Catálogo de facultades, escuelas e institutos universitarios."""
    list_display = ('nombre',)
    search_fields = ('nombre',)


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    """Catálogo de áreas de conocimiento y disciplinas académicas."""
    list_display = ('nombre',)
    search_fields = ('nombre',)


@admin.register(TipoContenido)
class TipoContenidoAdmin(admin.ModelAdmin):
    """Tipologías documentales (Artículos, Tesis, Ponencias, Capítulos de Libro)."""
    list_display = ('nombre',)
    search_fields = ('nombre',)
