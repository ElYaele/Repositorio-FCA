"""
====================================================================================================
SISTEMA DE REPOSITORIO ACADÉMICO INSTITUCIONAL (FCA - UABC)
Módulo: Pagina/urls.py
Descripción: Catálogo de Rutas y Endpoints Operativos de la Aplicación Central.
Autor: Facultad de Contaduría y Administración - Campus Tijuana
====================================================================================================
Este archivo mapea todas las URIs de la aplicación a sus correspondientes vistas y controladores.
Estructura funcional de los endpoints:

1. Catálogo Público y Búsqueda: Portada, metabúsqueda facetada, contacto institucional.
2. Carga y Edición de Obras: Asistente multipart, edición docente, acuses de recibo en PDF y métricas.
3. Ciclo de Autenticación y Cuentas: Registro institucional, OTP vía correo universitario, recuperación de
   contraseñas y solicitudes de reactivación.
4. Panel Docente (Mi Panel): Gestión de expediente académico, CV institucional en PDF, auxiliares de investigación.
5. Coautorías e Invitaciones: Confirmación y firma de coautorías, emisión de constancias oficiales.
6. Mensajería y Mesa de Ayuda: Comunicación bidireccional entre docentes, simulador de soporte y tickets.
7. Configuración Institucional: Administrador de avisos, carrusel de eventos FCA, FAQs, redes y enlaces.
8. Directorio del Claustro: Perfiles de profesores, felicitaciones y poemas de cumpleaños interactivos.
9. Panel de Control y Moderación: Flujo editorial (aprobación/rechazo de obras y semblanzas), bitácora inmutable,
   herramienta de fusión y deduplicación de autores, respaldos transaccionales ZIP/JSON y control de concurrencia.
====================================================================================================
"""

from django.urls import path
from .views import (
    HomePageView,
    ArticuloCreateView,
    ArticuloDocenteEditarView,
    acuse_recepcion_documento_view,
    BusquedaResultadosView,
    login_view,
    logout_view,
    solicitar_registro_view,
    verificar_codigo_registro_view,
    reenviar_codigo_registro_view,
    recuperar_password_view,
    validar_recuperar_password_view,
    mi_panel_view,
    actualizar_datos_cuenta_view,
    reporte_curriculo_pdf_view,
    gestionar_auxiliar_docente_view,
    actualizar_perfil_docente_view,
    cambiar_password_propia_view,
    directorio_profesores_view,
    enviar_felicitacion_cumpleanos_view,
    universidades_colaboradoras_view,
    panel_usuarios_view,
    ver_subidas_usuario_view,
    asignar_autor_propio_doc_view,
    restablecer_password_usuario_view,
    aprobar_usuario_view,
    rechazar_usuario_view,
    aprobar_cuenta_soporte_view,
    rechazar_cuenta_soporte_view,
    desactivar_cuenta_soporte_view,
    toggle_estado_usuario_view,
    toggle_superuser_view,
    eliminar_usuario_view,
    cambiar_rol_usuario_view,
    aprobar_documento_view,
    rechazar_documento_view,
    eliminar_documento_view,
    restaurar_documento_view,
    vaciar_papelera_documentos_view,
    marcar_archivo_checado_view,
    acciones_masivas_documentos_view,
    exportar_documentos_excel_view,
    exportar_auditoria_excel_view,
    historial_documento_api_view,
    exportar_respaldo_sistema_view,
    restaurar_respaldo_sistema_view,
    aprobar_semblanza_view,
    rechazar_semblanza_view,
    editar_semblanza_admin_view,
    restablecer_semblanza_admin_view,
    crear_autor_rapido_view,
    editar_ficha_usuario_admin_view,
    suspender_usuario_view,
    reactivar_usuario_view,
    solicitar_reactivacion_view,
    toggle_trusted_publisher_view,
    desactivar_cuenta_propia_view,
    gestion_coautorias_view,
    responder_invitacion_coautoria_view,
    aceptar_todas_coautorias_view,
    cancelar_invitacion_coautoria_view,
    enviar_recordatorio_coautoria_view,
    exportar_coautorias_csv_view,
    constancia_coautoria_view,
    mensajeria_view,
    soporte_institucional_view,
    enviar_mensaje_interno_view,
    marcar_mensaje_leido_view,
    obtener_mensajes_nuevos_ajax_view,
    cambiar_estado_soporte_view,
    fusionar_autores_view,
    revertir_fusion_view,
    limpiar_autores_huerfanos_admin_view,
    eliminar_autor_huerfano_individual_view,
    cambiar_color_cumpleanos_view,
    impersonar_usuario_view,
    dejar_impersonacion_view,
    bitacora_usuario_ajax_view,
    sync_panel_usuarios_ajax_view,
    buscar_autores_live_ajax_view,
    verificar_titulo_duplicado_ajax_view,
    configuracion_soporte_view,
    probar_email_soporte_ajax,
    crear_faq_soporte_view,
    editar_faq_soporte_view,
    eliminar_faq_soporte_view,
    toggle_faq_soporte_view,
    crear_evento_fca_view,
    editar_evento_fca_view,
    eliminar_evento_fca_view,
    toggle_evento_fca_view,
    crear_enlace_rapido_view,
    editar_enlace_rapido_view,
    eliminar_enlace_rapido_view,
    toggle_enlace_rapido_view,
    crear_red_social_view,
    editar_red_social_view,
    eliminar_red_social_view,
    toggle_red_social_view,
    reordenar_red_social_view,
    crear_enlace_footer_view,
    editar_enlace_footer_view,
    eliminar_enlace_footer_view,
    toggle_enlace_footer_view,
    reordenar_enlace_footer_view,
    reordenar_footer_dragdrop_ajax,
    contacto_view,
    cambiar_estado_contacto_view,
    toggle_politica_acceso_view,
    obtener_metricas_semestre_api,
    registrar_auditoria_semestral_view,
    dictamen_semestral_pdf_view,
    api_presencia_heartbeat_view,
    api_bloqueo_concurrencia_view,
    toggle_permiso_moderador_view,
    registrar_metrica_obra_view,
)

urlpatterns = [
    # ==============================================================================================
    # 1. PÁGINA DE INICIO, BÚSQUEDA Y METADATOS PÚBLICOS
    # ==============================================================================================
    path("", HomePageView.as_view(), name='Home'),
    path('busqueda/', BusquedaResultadosView.as_view(), name='resultado_busqueda'),
    path('contacto/', contacto_view, name='contacto'),

    # ==============================================================================================
    # 2. GESTIÓN Y CARGA DE OBRAS ACADÉMICAS
    # ==============================================================================================
    path('upload/', ArticuloCreateView.as_view(), name='upload_document'),
    path('documento/editar/<int:pk>/', ArticuloDocenteEditarView.as_view(), name='editar_documento'),
    path('documento/<int:doc_id>/acuse/', acuse_recepcion_documento_view, name='acuse_recepcion'),
    path('api/obra/<int:doc_id>/metrica/', registrar_metrica_obra_view, name='registrar_metrica_obra'),

    # ==============================================================================================
    # 3. AUTENTICACIÓN, REGISTRO Y GESTIÓN DE CREDENCIALES
    # ==============================================================================================
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('solicitar-cuenta/', solicitar_registro_view, name='solicitar_registro'),
    path('verificar-cuenta/<int:user_id>/', verificar_codigo_registro_view, name='verificar_codigo_registro'),
    path('verificar-cuenta/reenviar/<int:user_id>/', reenviar_codigo_registro_view, name='reenviar_codigo_registro'),
    path('recuperar-contrasena/', recuperar_password_view, name='recuperar_password'),
    path('recuperar-contrasena/validar/<int:user_id>/', validar_recuperar_password_view, name='validar_recuperar_password'),
    path('solicitar-reactivacion/', solicitar_reactivacion_view, name='solicitar_reactivacion'),

    # ==============================================================================================
    # 4. PANEL PERSONAL DEL DOCENTE (MI PANEL)
    # ==============================================================================================
    path('mi-panel/', mi_panel_view, name='mi_panel'),
    path('mi-panel/actualizar-datos-cuenta/', actualizar_datos_cuenta_view, name='actualizar_datos_cuenta'),
    path('mi-panel/reporte-curriculo/', reporte_curriculo_pdf_view, name='reporte_curriculo_pdf'),
    path('mi-panel/actualizar-perfil/', actualizar_perfil_docente_view, name='actualizar_perfil_docente'),
    path('mi-panel/cambiar-clave/', cambiar_password_propia_view, name='cambiar_password_propia'),
    path('mi-panel/desactivar-cuenta/', desactivar_cuenta_propia_view, name='desactivar_cuenta_propia'),
    path('mi-panel/auxiliares/<int:auxiliar_id>/gestionar/', gestionar_auxiliar_docente_view, name='gestionar_auxiliar_docente'),
    path('mi-panel/coautoria/<int:invitacion_id>/', responder_invitacion_coautoria_view, name='responder_invitacion_coautoria_legacy'),
    path('mi-panel/mensajes/enviar/', enviar_mensaje_interno_view, name='enviar_mensaje_interno_legacy'),
    path('mi-panel/mensajes/marcar-leido/<int:mensaje_id>/', marcar_mensaje_leido_view, name='marcar_mensaje_leido_legacy'),

    # ==============================================================================================
    # 5. MÓDULO DE COAUTORÍAS E INVITACIONES ACADÉMICAS
    # ==============================================================================================
    path('coautorias/', gestion_coautorias_view, name='gestion_coautorias'),
    path('coautorias/<int:invitacion_id>/responder/', responder_invitacion_coautoria_view, name='responder_invitacion_coautoria'),
    path('coautorias/aceptar-todas/', aceptar_todas_coautorias_view, name='aceptar_todas_coautorias'),
    path('coautorias/<int:invitacion_id>/cancelar/', cancelar_invitacion_coautoria_view, name='cancelar_invitacion_coautoria'),
    path('coautorias/<int:invitacion_id>/recordar/', enviar_recordatorio_coautoria_view, name='enviar_recordatorio_coautoria'),
    path('coautorias/exportar-csv/', exportar_coautorias_csv_view, name='exportar_coautorias_csv'),
    path('coautorias/<int:invitacion_id>/constancia/', constancia_coautoria_view, name='constancia_coautoria'),

    # ==============================================================================================
    # 6. MENSAJERÍA ACADÉMICA INTERNA Y NOTIFICACIONES
    # ==============================================================================================
    path('mensajeria/', mensajeria_view, name='mensajeria'),
    path('mensajeria/enviar/', enviar_mensaje_interno_view, name='enviar_mensaje_interno'),
    path('mensajeria/marcar-leido/<int:mensaje_id>/', marcar_mensaje_leido_view, name='marcar_mensaje_leido'),
    path('mensajeria/obtener-nuevos/', obtener_mensajes_nuevos_ajax_view, name='obtener_mensajes_nuevos_ajax'),

    # ==============================================================================================
    # 7. MÓDULO DE SOPORTE INSTITUCIONAL Y MESA DE AYUDA
    # ==============================================================================================
    path('soporte/', soporte_institucional_view, name='soporte_institucional'),
    path('soporte/estado/<int:ticket_autor_id>/', cambiar_estado_soporte_view, name='cambiar_estado_soporte'),

    # ==============================================================================================
    # 8. CONFIGURACIÓN DEL SISTEMA Y GESTIÓN DE CONTENIDOS INSTITUCIONALES
    # ==============================================================================================
    path('configuracion-soporte/', configuracion_soporte_view, name='configuracion_soporte'),
    path('configuracion-soporte/probar-email/', probar_email_soporte_ajax, name='probar_email_soporte_ajax'),
    path('configuracion-soporte/faq/crear/', crear_faq_soporte_view, name='crear_faq_soporte'),
    path('configuracion-soporte/faq/editar/<int:faq_id>/', editar_faq_soporte_view, name='editar_faq_soporte'),
    path('configuracion-soporte/faq/eliminar/<int:faq_id>/', eliminar_faq_soporte_view, name='eliminar_faq_soporte'),
    path('configuracion-soporte/faq/toggle/<int:faq_id>/', toggle_faq_soporte_view, name='toggle_faq_soporte'),

    # Carrusel de Eventos FCA
    path('configuracion-soporte/evento/crear/', crear_evento_fca_view, name='crear_evento_fca'),
    path('configuracion-soporte/evento/editar/<int:evento_id>/', editar_evento_fca_view, name='editar_evento_fca'),
    path('configuracion-soporte/evento/eliminar/<int:evento_id>/', eliminar_evento_fca_view, name='eliminar_evento_fca'),
    path('configuracion-soporte/evento/toggle/<int:evento_id>/', toggle_evento_fca_view, name='toggle_evento_fca'),

    # Enlaces Rápidos Institucionales
    path('configuracion-soporte/enlace/crear/', crear_enlace_rapido_view, name='crear_enlace_rapido'),
    path('configuracion-soporte/enlace/editar/<int:enlace_id>/', editar_enlace_rapido_view, name='editar_enlace_rapido'),
    path('configuracion-soporte/enlace/eliminar/<int:enlace_id>/', eliminar_enlace_rapido_view, name='eliminar_enlace_rapido'),
    path('configuracion-soporte/enlace/toggle/<int:enlace_id>/', toggle_enlace_rapido_view, name='toggle_enlace_rapido'),

    # Redes Sociales Universitarias
    path('configuracion-soporte/red-social/crear/', crear_red_social_view, name='crear_red_social'),
    path('configuracion-soporte/red-social/editar/<int:red_id>/', editar_red_social_view, name='editar_red_social'),
    path('configuracion-soporte/red-social/eliminar/<int:red_id>/', eliminar_red_social_view, name='eliminar_red_social'),
    path('configuracion-soporte/red-social/toggle/<int:red_id>/', toggle_red_social_view, name='toggle_red_social'),
    path('configuracion-soporte/red-social/reordenar/<int:red_id>/<str:direccion>/', reordenar_red_social_view, name='reordenar_red_social'),

    # Enlaces del Pie de Página (Footer Dinámico)
    path('configuracion-soporte/enlace-footer/crear/', crear_enlace_footer_view, name='crear_enlace_footer'),
    path('configuracion-soporte/enlace-footer/editar/<int:enlace_id>/', editar_enlace_footer_view, name='editar_enlace_footer'),
    path('configuracion-soporte/enlace-footer/eliminar/<int:enlace_id>/', eliminar_enlace_footer_view, name='eliminar_enlace_footer'),
    path('configuracion-soporte/enlace-footer/toggle/<int:enlace_id>/', toggle_enlace_footer_view, name='toggle_enlace_footer'),
    path('configuracion-soporte/enlace-footer/reordenar/<int:enlace_id>/<str:direccion>/', reordenar_enlace_footer_view, name='reordenar_enlace_footer'),
    path('configuracion-soporte/footer/guardar-orden-dragdrop/', reordenar_footer_dragdrop_ajax, name='reordenar_footer_dragdrop_ajax'),
    path('configuracion-soporte/contacto/<int:contacto_id>/', cambiar_estado_contacto_view, name='cambiar_estado_contacto'),

    # ==============================================================================================
    # 9. DIRECTORIO DEL CLAUSTRO PROFESORAL Y CUMPLEAÑOS
    # ==============================================================================================
    path('profesores/', directorio_profesores_view, name='directorio_profesores'),
    path('profesores/felicitar/<int:autor_id>/', enviar_felicitacion_cumpleanos_view, name='enviar_felicitacion_cumpleanos'),
    path('profesores/color-cumpleanos/', cambiar_color_cumpleanos_view, name='cambiar_color_cumpleanos'),

    # ==============================================================================================
    # 10. RED DE UNIVERSIDADES COLABORADORAS
    # ==============================================================================================
    path('universidades-colaboradoras/', universidades_colaboradoras_view, name='universidades_colaboradoras'),

    # ==============================================================================================
    # 11. PANEL DE CONTROL, AUDITORÍA Y GESTIÓN DE USUARIOS
    # ==============================================================================================
    path('gestion-usuarios/', panel_usuarios_view, name='panel_usuarios'),
    path('gestion-usuarios/politicas-acceso/', toggle_politica_acceso_view, name='toggle_politica_acceso'),
    path('gestion-usuarios/auditoria-semestral/registrar/', registrar_auditoria_semestral_view, name='registrar_auditoria_semestral'),
    path('gestion-usuarios/auditoria-semestral/metricas-api/', obtener_metricas_semestre_api, name='obtener_metricas_semestre_api'),
    path('gestion-usuarios/auditoria-semestral/<int:auditoria_id>/dictamen-pdf/', dictamen_semestral_pdf_view, name='dictamen_semestral_pdf'),
    path('gestion-usuarios/fusionar-autores/', fusionar_autores_view, name='fusionar_autores'),
    path('gestion-usuarios/revertir-fusion/<int:fusion_id>/', revertir_fusion_view, name='revertir_fusion'),
    path('gestion-usuarios/limpiar-autores-huerfanos/', limpiar_autores_huerfanos_admin_view, name='limpiar_autores_huerfanos_admin'),
    path('gestion-usuarios/eliminar-autor-huerfano/<int:autor_id>/', eliminar_autor_huerfano_individual_view, name='eliminar_autor_huerfano_individual'),
    path('gestion-usuarios/ver-subidas/<int:user_id>/', ver_subidas_usuario_view, name='ver_subidas_usuario'),
    path('gestion-usuarios/asignar-autor-propio/<int:doc_id>/<int:user_id>/', asignar_autor_propio_doc_view, name='asignar_autor_propio_doc'),
    path('gestion-usuarios/cambiar-clave/<int:user_id>/', restablecer_password_usuario_view, name='restablecer_password_usuario'),
    path('gestion-usuarios/editar-ficha/<int:user_id>/', editar_ficha_usuario_admin_view, name='editar_ficha_usuario_admin'),
    path('gestion-usuarios/aprobar/<int:user_id>/', aprobar_usuario_view, name='aprobar_usuario'),
    path('gestion-usuarios/rechazar/<int:user_id>/', rechazar_usuario_view, name='rechazar_usuario'),
    path('gestion-usuarios/aprobar-soporte/<int:user_id>/', aprobar_cuenta_soporte_view, name='aprobar_cuenta_soporte'),
    path('gestion-usuarios/rechazar-soporte/<int:user_id>/', rechazar_cuenta_soporte_view, name='rechazar_cuenta_soporte'),
    path('gestion-usuarios/desactivar-soporte/<int:user_id>/', desactivar_cuenta_soporte_view, name='desactivar_cuenta_soporte'),
    path('gestion-usuarios/suspender/<int:user_id>/', suspender_usuario_view, name='suspender_usuario'),
    path('gestion-usuarios/reactivar/<int:user_id>/', reactivar_usuario_view, name='reactivar_usuario'),
    path('gestion-usuarios/toggle-trusted/<int:user_id>/', toggle_trusted_publisher_view, name='toggle_trusted_publisher'),
    path('gestion-usuarios/toggle/<int:user_id>/', toggle_estado_usuario_view, name='toggle_estado_usuario'),
    path('gestion-usuarios/toggle-super/<int:user_id>/', toggle_superuser_view, name='toggle_superuser'),
    path('gestion-usuarios/cambiar-rol/<int:user_id>/', cambiar_rol_usuario_view, name='cambiar_rol_usuario'),
    path('gestion-usuarios/eliminar/<int:user_id>/', eliminar_usuario_view, name='eliminar_usuario'),
    path('gestion-usuarios/impersonar/<int:user_id>/', impersonar_usuario_view, name='impersonar_usuario'),
    path('gestion-usuarios/dejar-impersonacion/', dejar_impersonacion_view, name='dejar_impersonacion'),
    path('gestion-usuarios/bitacora/<int:user_id>/', bitacora_usuario_ajax_view, name='bitacora_usuario_ajax'),

    # ==============================================================================================
    # 12. GESTIÓN EDITORIAL Y MODERACIÓN DE DOCUMENTOS
    # ==============================================================================================
    path('gestion-documentos/aprobar/<int:doc_id>/', aprobar_documento_view, name='aprobar_documento'),
    path('gestion-documentos/rechazar/<int:doc_id>/', rechazar_documento_view, name='rechazar_documento'),
    path('gestion-documentos/eliminar/<int:doc_id>/', eliminar_documento_view, name='eliminar_documento'),
    path('gestion-documentos/restaurar/<int:doc_id>/', restaurar_documento_view, name='restaurar_documento'),
    path('gestion-documentos/vaciar-papelera/', vaciar_papelera_documentos_view, name='vaciar_papelera_documentos'),
    path('gestion-documentos/marcar-checado/<int:doc_id>/', marcar_archivo_checado_view, name='marcar_archivo_checado'),
    path('gestion-documentos/acciones-masivas/', acciones_masivas_documentos_view, name='acciones_masivas_documentos'),
    path('gestion-documentos/exportar-excel/', exportar_documentos_excel_view, name='exportar_documentos_excel'),
    path('gestion-auditoria/exportar-excel/', exportar_auditoria_excel_view, name='exportar_auditoria_excel'),
    path('gestion-documentos/<int:doc_id>/historial/', historial_documento_api_view, name='historial_documento_api'),
    path('gestion-sistema/exportar-respaldo/', exportar_respaldo_sistema_view, name='exportar_respaldo_sistema'),
    path('gestion-sistema/restaurar-respaldo/', restaurar_respaldo_sistema_view, name='restaurar_respaldo_sistema'),

    # ==============================================================================================
    # 13. MODERACIÓN EDITORIAL DE SEMBLANZAS Y PERFILES DOCENTES
    # ==============================================================================================
    path('gestion-semblanzas/aprobar/<int:autor_id>/', aprobar_semblanza_view, name='aprobar_semblanza'),
    path('gestion-semblanzas/rechazar/<int:autor_id>/', rechazar_semblanza_view, name='rechazar_semblanza'),
    path('gestion-semblanzas/editar/<int:autor_id>/', editar_semblanza_admin_view, name='editar_semblanza_admin'),
    path('gestion-semblanzas/eliminar/<int:autor_id>/', restablecer_semblanza_admin_view, name='restablecer_semblanza_admin'),

    # ==============================================================================================
    # 14. ENDPOINTS REACTIVOS AJAX / JSON Y UTILIDADES
    # ==============================================================================================
    path('ajax/crear-autor-rapido/', crear_autor_rapido_view, name='crear_autor_rapido'),
    path('ajax/buscar-autores-live/', buscar_autores_live_ajax_view, name='buscar_autores_live_ajax'),
    path('ajax/verificar-titulo-duplicado/', verificar_titulo_duplicado_ajax_view, name='verificar_titulo_duplicado_ajax'),
    path('gestion-usuarios/sync-ajax/', sync_panel_usuarios_ajax_view, name='sync_panel_usuarios_ajax'),

    # Control de Presencia, Concurrencia y Permisos Granulares
    path('api/presencia/heartbeat/', api_presencia_heartbeat_view, name='api_presencia_heartbeat'),
    path('api/presencia/bloqueo/', api_bloqueo_concurrencia_view, name='api_bloqueo_concurrencia'),
    path('api/moderadores/toggle-permiso/', toggle_permiso_moderador_view, name='toggle_permiso_moderador'),
]
