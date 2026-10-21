from django.contrib import admin
from .models import (
    Articulo, Entidad, Area, TipoContenido, Autor, MensajeCumpleanos,
    Nombramiento, EnlaceProfesional, RegistroAuditoria, Universidad
)

@admin.register(Articulo)
class ArticuloAdmin(admin.ModelAdmin):
    filter_horizontal = ('autor',)  # Tu excelente configuración para seleccionar múltiples autores
    list_display = ('titulo', 'estado', 'tipo_contenido', 'año_produccion', 'entidad', 'subido_por', 'created_at')
    search_fields = ('titulo', 'descripcion', 'autor__nombre')
    list_filter = ('estado', 'tipo_contenido', 'entidad', 'area', 'año_produccion')
    ordering = ('-created_at',)

@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'correo', 'numero_empleado', 'institucion_origen', 'es_profesor', 'estado_semblanza')
    search_fields = ('nombre', 'correo', 'numero_empleado', 'institucion_origen')
    list_filter = ('es_profesor', 'es_externo', 'estado_semblanza', 'genero')

@admin.register(Universidad)
class UniversidadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'siglas')
    search_fields = ('nombre', 'siglas')

from .views import es_superusuario_principal

# RESTRICCIÓN DE SEGURIDAD EXCLUSIVA: Solo el Superadministrador Principal puede acceder a /admin/
original_admin_has_permission = admin.site.has_permission

def admin_site_exclusivo_superadmin_principal(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not user.is_active or not user.is_superuser:
        return False
    return es_superusuario_principal(user)

admin.site.has_permission = admin_site_exclusivo_superadmin_principal


@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('accion', 'admin_usuario', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('accion', 'detalle')
    ordering = ('-created_at',)
    actions = None  # Deshabilita acciones en masa (ej. "Eliminar registros seleccionados")

    def has_add_permission(self, request):
        # Nadie puede crear auditorías manuales desde el admin; solo el sistema las genera
        return False

    def has_change_permission(self, request, obj=None):
        # Bitácora inmutable: nadie puede alterar el contenido de una auditoría
        return False

    def has_delete_permission(self, request, obj=None):
        # Inmutable contra borrados: nadie puede eliminar registros de auditoría
        return False

    def get_readonly_fields(self, request, obj=None):
        # Todos los campos son estrictamente de solo lectura
        return [f.name for f in self.model._meta.fields]

@admin.register(MensajeCumpleanos)
class MensajeCumpleanosAdmin(admin.ModelAdmin):
    list_display = ('para_docente', 'de_usuario', 'fecha_envio')
    list_filter = ('fecha_envio',)
    search_fields = ('mensaje',)

@admin.register(Nombramiento)
class NombramientoAdmin(admin.ModelAdmin):
    list_display = ('autor', 'rol')
    list_filter = ('rol',)

@admin.register(EnlaceProfesional)
class EnlaceProfesionalAdmin(admin.ModelAdmin):
    list_display = ('autor', 'plataforma', 'url')
    search_fields = ('plataforma', 'url')

# Catálogos básicos con barra de búsqueda
@admin.register(Entidad)
class EntidadAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)

@admin.register(TipoContenido)
class TipoContenidoAdmin(admin.ModelAdmin):
    list_display = ('nombre',)
    search_fields = ('nombre',)