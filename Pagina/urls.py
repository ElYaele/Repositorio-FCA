from django.urls import path
from .views import (
    HomePageView,
    ArticuloCreateView,
    ArticuloDocenteEditarView,
    BusquedaResultadosView,
    login_view,
    logout_view,
    solicitar_registro_view,
    mi_panel_view,
    actualizar_perfil_docente_view,
    cambiar_password_propia_view,
    directorio_profesores_view,
    enviar_felicitacion_cumpleanos_view,
    universidades_colaboradoras_view,
    panel_usuarios_view,
    ver_subidas_usuario_view,
    restablecer_password_usuario_view,
    aprobar_usuario_view,
    rechazar_usuario_view,
    toggle_estado_usuario_view,
    toggle_superuser_view,
    eliminar_usuario_view,
    cambiar_rol_usuario_view,
    aprobar_documento_view,
    rechazar_documento_view,
    eliminar_documento_view,
    aprobar_semblanza_view,
    rechazar_semblanza_view,
    editar_semblanza_admin_view,
    restablecer_semblanza_admin_view,
    crear_autor_rapido_view,
    editar_ficha_usuario_admin_view,
)

urlpatterns = [
    path("", HomePageView.as_view(), name='Home'),
    path('busqueda/', BusquedaResultadosView.as_view(), name='resultado_busqueda'),
    path('upload/', ArticuloCreateView.as_view(), name='upload_document'),
    path('documento/editar/<int:pk>/', ArticuloDocenteEditarView.as_view(), name='editar_documento'),

    # Autenticación y Registro
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('solicitar-cuenta/', solicitar_registro_view, name='solicitar_registro'),

    # Panel personal de docente / usuario
    path('mi-panel/', mi_panel_view, name='mi_panel'),
    path('mi-panel/actualizar-perfil/', actualizar_perfil_docente_view, name='actualizar_perfil_docente'),
    path('mi-panel/cambiar-clave/', cambiar_password_propia_view, name='cambiar_password_propia'),

    # Directorio de profesores y cumpleaños
    path('profesores/', directorio_profesores_view, name='directorio_profesores'),
    path('profesores/felicitar/<int:autor_id>/', enviar_felicitacion_cumpleanos_view, name='enviar_felicitacion_cumpleanos'),

    # Red de Universidades Colaboradoras
    path('universidades-colaboradoras/', universidades_colaboradoras_view, name='universidades_colaboradoras'),

    # Panel de administración (Superusuario)
    path('gestion-usuarios/', panel_usuarios_view, name='panel_usuarios'),
    path('gestion-usuarios/ver-subidas/<int:user_id>/', ver_subidas_usuario_view, name='ver_subidas_usuario'),
    path('gestion-usuarios/cambiar-clave/<int:user_id>/', restablecer_password_usuario_view, name='restablecer_password_usuario'),
    path('gestion-usuarios/editar-ficha/<int:user_id>/', editar_ficha_usuario_admin_view, name='editar_ficha_usuario_admin'),
    path('gestion-usuarios/aprobar/<int:user_id>/', aprobar_usuario_view, name='aprobar_usuario'),
    path('gestion-usuarios/rechazar/<int:user_id>/', rechazar_usuario_view, name='rechazar_usuario'),
    path('gestion-usuarios/toggle/<int:user_id>/', toggle_estado_usuario_view, name='toggle_estado_usuario'),
    path('gestion-usuarios/toggle-super/<int:user_id>/', toggle_superuser_view, name='toggle_superuser'),
    path('gestion-usuarios/cambiar-rol/<int:user_id>/', cambiar_rol_usuario_view, name='cambiar_rol_usuario'),
    path('gestion-usuarios/eliminar/<int:user_id>/', eliminar_usuario_view, name='eliminar_usuario'),

    # Moderación de documentos
    path('gestion-documentos/aprobar/<int:doc_id>/', aprobar_documento_view, name='aprobar_documento'),
    path('gestion-documentos/rechazar/<int:doc_id>/', rechazar_documento_view, name='rechazar_documento'),
    path('gestion-documentos/eliminar/<int:doc_id>/', eliminar_documento_view, name='eliminar_documento'),

    # Moderación de semblanzas (Claustro)
    path('gestion-semblanzas/aprobar/<int:autor_id>/', aprobar_semblanza_view, name='aprobar_semblanza'),
    path('gestion-semblanzas/rechazar/<int:autor_id>/', rechazar_semblanza_view, name='rechazar_semblanza'),
    path('gestion-semblanzas/editar/<int:autor_id>/', editar_semblanza_admin_view, name='editar_semblanza_admin'),
    path('gestion-semblanzas/eliminar/<int:autor_id>/', restablecer_semblanza_admin_view, name='restablecer_semblanza_admin'),

    # API para autores
    path('ajax/crear-autor-rapido/', crear_autor_rapido_view, name='crear_autor_rapido'),
]