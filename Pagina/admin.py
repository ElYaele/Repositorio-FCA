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

@admin.register(RegistroAuditoria)
class RegistroAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('accion', 'admin_usuario', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('accion', 'detalle')
    ordering = ('-created_at',)

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