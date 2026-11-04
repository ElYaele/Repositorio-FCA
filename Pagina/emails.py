import os
import logging
import threading
import json
import urllib.request
import urllib.error
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

def generar_html_base(titulo_cabecera, subtitulo, contenido_cuerpo_html, boton_texto=None, boton_url=None):
    """
    Plantilla HTML base con diseño institucional UABC (Verde #006633, Dorado #dd971a).
    Responsiva, limpia y compatible con clientes de correo modernos (Gmail, Outlook, Apple Mail).
    """
    url_btn = boton_url or "http://127.0.0.1:8000/login/"
    boton_html = ""
    if boton_texto:
        boton_html = f"""
        <div style="text-align: center; margin: 30px 0 20px 0;">
            <a href="{url_btn}" style="background-color: #006633; color: #ffffff; padding: 13px 28px; text-decoration: none; font-size: 14px; font-weight: bold; border-radius: 25px; display: inline-block; box-shadow: 0 4px 10px rgba(0,102,51,0.25);">
                {boton_texto} &rarr;
            </a>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{titulo_cabecera}</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f4f6f9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #333333; line-height: 1.6;">
        <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #f4f6f9; padding: 25px 10px;">
            <tr>
                <td align="center">
                    <table border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08); border-top: 5px solid #dd971a;">
                        
                        <!-- ENCABEZADO INSTITUCIONAL -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #006633 0%, #004d26 100%); padding: 28px 30px; text-align: center; color: #ffffff;">
                                <div style="font-size: 11px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; color: #dd971a; margin-bottom: 6px;">
                                    Universidad Autónoma de Baja California
                                </div>
                                <h1 style="margin: 0; font-size: 20px; font-weight: 700; color: #ffffff; line-height: 1.3;">
                                    {titulo_cabecera}
                                </h1>
                                <p style="margin: 6px 0 0 0; font-size: 13px; color: #d1e7dd;">
                                    {subtitulo}
                                </p>
                            </td>
                        </tr>

                        <!-- CUERPO PRINCIPAL -->
                        <tr>
                            <td style="padding: 32px 30px 25px 30px; font-size: 14px; color: #444444;">
                                {contenido_cuerpo_html}
                                {boton_html}
                            </td>
                        </tr>

                        <!-- PIE INSTITUCIONAL -->
                        <tr>
                            <td style="background-color: #f8faf9; padding: 20px 30px; text-align: center; border-top: 1px solid #e9ecef; font-size: 11px; color: #6c757d;">
                                <strong style="color: #006633;">Repositorio Académico Institucional FCA</strong><br>
                                Facultad de Contaduría y Administración &bull; Campus Tijuana<br>
                                <span style="color: #999999;">Este es un mensaje institucional automático. Por favor no respondas directamente a este correo.</span>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


def obtener_config_envio_correo():
    """
    Obtiene las credenciales dinámicas de la base de datos (ConfiguracionSistema)
    o retorna None si no están disponibles para usar el fallback de settings/env.
    """
    try:
        from Pagina.models import ConfiguracionSistema
        config = ConfiguracionSistema.get_solo()
        if config and config.email_host_user:
            return config
    except Exception:
        pass
    return None

def probar_conexion_smtp(destinatario_prueba, host=None, port=None, username=None, password=None, use_tls=True, use_ssl=False, remitente_nombre="Repositorio FCA UABC"):
    """
    Envía un correo de prueba sincrónico para verificar la validez de las credenciales de Gmail/SMTP.
    Devuelve (True, "Mensaje de éxito") o (False, "Detalle del error").
    """
    from datetime import datetime
    from django.core.mail import get_connection
    try:
        puerto_num = int(port or 587)
        # Salvaguarda: TLS y SSL son mutuamente excluyentes en Django
        if use_tls and use_ssl:
            if puerto_num == 465:
                use_tls = False
            else:
                use_ssl = False

        conn = get_connection(
            backend='django.core.mail.backends.smtp.EmailBackend',
            host=host or 'smtp.gmail.com',
            port=puerto_num,
            username=username,
            password=password,
            use_tls=use_tls,
            use_ssl=use_ssl,
            timeout=8
        )
        asunto = "✅ Prueba de Conexión Exitosa - Repositorio FCA UABC"
        texto = f"¡Hola!\n\nEste correo confirma que la configuración de envío automático de Gmail ha sido configurada con éxito en el Repositorio Institucional FCA UABC.\n\nRemitente activo: {username}\nFecha y hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\nNo es necesario responder a este mensaje."
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #00723F; margin-bottom: 4px;">Universidad Autónoma de Baja California</h2>
                <p style="color: #64748b; font-size: 14px; margin: 0;">Facultad de Contaduría y Administración &bull; Repositorio Institucional</p>
            </div>
            <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 18px; margin-bottom: 20px; text-align: center;">
                <h3 style="color: #065f46; margin: 0 0 6px 0;">¡Conexión y Envío Exitosos!</h3>
                <p style="color: #047857; font-size: 14px; margin: 0;">El correo automático de Gmail se encuentra activo y listo para emitir notificaciones y códigos de verificación.</p>
            </div>
            <p style="color: #334155; font-size: 14px; line-height: 1.6;">
                <strong>Detalles de la conexión:</strong><br>
                &bull; <strong>Remitente configurado:</strong> {username}<br>
                &bull; <strong>Nombre de visualización:</strong> {remitente_nombre}<br>
                &bull; <strong>Servidor / Puerto:</strong> {host}:{port}<br>
                &bull; <strong>Seguridad:</strong> {'TLS (587)' if use_tls else ('SSL (465)' if use_ssl else 'Estándar')}
            </p>
            <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 25px 0;">
            <p style="color: #94a3b8; font-size: 12px; text-align: center; margin: 0;">
                Este es un mensaje de prueba generado por el Super Administrador desde el panel de Configuración y Soporte.
            </p>
        </div>
        """
        msg = EmailMultiAlternatives(
            subject=asunto,
            body=texto,
            from_email=f"{remitente_nombre} <{username}>",
            to=[destinatario_prueba],
            connection=conn
        )
        msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=False)
        return True, f"Correo de prueba enviado con éxito a {destinatario_prueba}."
    except Exception as e:
        error_str = str(e)
        if "Username and Password not accepted" in error_str or "535" in error_str:
            error_str = "Google rechazó las credenciales (Error 535). Asegúrate de usar una 'Contraseña de Aplicación' de 16 caracteres de Google y tener activada la Verificación en 2 Pasos en la cuenta de Gmail."
        elif "Connection refused" in error_str or "timed out" in error_str:
            error_str = f"No se pudo conectar al servidor {host}:{port}. Verifica tu conexión o el puerto SMTP."
        return False, f"Fallo al enviar correo: {error_str}"

def enviar_correo_institucional(destinatario, asunto, texto_plano, html_cuerpo, asincrono=True, reply_to=None):
    """
    Envía un correo electrónico multipart (texto + HTML) de manera segura.
    Soporta:
    1. Brevo REST API (HTTPS / Puerto 443) si está configurado BREVO_API_KEY.
    2. Configuración dinámica en BD (ConfiguracionSistema) o Django SMTP estándar con timeout seguro.
    3. Envío asíncrono en hilo secundario (daemon thread).
    """
    if not destinatario:
        return False

    def _ejecutar_envio():
        config_db = obtener_config_envio_correo()

        # 1. Intentar envío por API HTTP (Brevo) si existe API Key (pasa por puerto 443 en Render Free)
        brevo_api_key = (
            os.getenv('BREVO_API_KEY') or 
            os.getenv('BREVO API KEY') or 
            os.getenv('BREVO_KEY') or 
            os.getenv('SENDINBLUE_API_KEY') or 
            ''
        ).strip().strip("'\"")

        if brevo_api_key:
            try:
                remitente_correo = (config_db.email_host_user if config_db and config_db.email_host_user else os.getenv('EMAIL_HOST_USER', 'pruebarepsoitoriofca@gmail.com')).strip()
                remitente_nombre = (config_db.email_remitente_nombre if config_db and config_db.email_remitente_nombre else "Repositorio FCA UABC").strip()
                to_list = [{"email": d.strip()} for d in (destinatario if isinstance(destinatario, list) else [destinatario]) if d.strip()]
                payload = {
                    "sender": {"name": remitente_nombre, "email": remitente_correo},
                    "to": to_list,
                    "subject": asunto,
                    "htmlContent": html_cuerpo,
                    "textContent": texto_plano
                }
                if reply_to:
                    payload["replyTo"] = {"email": reply_to.strip()}
                req = urllib.request.Request(
                    "https://api.brevo.com/v3/smtp/email",
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        "accept": "application/json",
                        "api-key": brevo_api_key,
                        "content-type": "application/json"
                    },
                    method='POST'
                )
                with urllib.request.urlopen(req, timeout=6) as response:
                    if response.status in (200, 201):
                        logger.info(f"[BREVO API HTTPS] Correo enviado exitosamente a {destinatario}: {asunto}")
                        return True
            except urllib.error.HTTPError as e_api:
                try:
                    cuerpo_error = e_api.read().decode('utf-8')
                except Exception:
                    cuerpo_error = str(e_api)
                logger.warning(f"[BREVO API HTTPS] Error al enviar vía API HTTP ({e_api.code}): {cuerpo_error}. Intentando SMTP estándar...")
            except Exception as e_api:
                logger.warning(f"[BREVO API HTTPS] Error general al enviar vía API HTTP: {e_api}. Intentando SMTP estándar...")

        # 2. Envío por SMTP estándar (Usando credenciales de la BD si están disponibles)
        if config_db and config_db.email_host_user and config_db.email_host_password:
            remitente = f"{config_db.email_remitente_nombre} <{config_db.email_host_user}>"
            from django.core.mail import get_connection
            puerto_db = int(config_db.email_port or 587)
            use_tls_db = config_db.email_use_tls
            use_ssl_db = config_db.email_use_ssl
            if use_tls_db and use_ssl_db:
                if puerto_db == 465:
                    use_tls_db = False
                else:
                    use_ssl_db = False

            backend = get_connection(
                backend='django.core.mail.backends.smtp.EmailBackend',
                host=config_db.email_host or 'smtp.gmail.com',
                port=puerto_db,
                username=config_db.email_host_user,
                password=config_db.email_host_password,
                use_tls=use_tls_db,
                use_ssl=use_ssl_db,
                timeout=getattr(settings, 'EMAIL_TIMEOUT', 6)
            )
        else:
            remitente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Repositorio FCA UABC <notificaciones.fca.uabc@gmail.com>')
            password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
            if not password and getattr(settings, 'EMAIL_BACKEND', '') == 'django.core.mail.backends.smtp.EmailBackend':
                from django.core.mail.backends.console import EmailBackend as ConsoleBackend
                backend = ConsoleBackend()
                logger.warning(
                    f"[MODO CONSOLA] EMAIL_HOST_PASSWORD no está configurado (¿falta agregar las variables en el Dashboard de Render?). "
                    f"El correo para {destinatario} con asunto '{asunto}' se imprimirá en los logs de la consola en lugar de enviarse por Gmail."
                )
            else:
                backend = None

        try:
            reply_to_list = None
            if reply_to:
                reply_to_list = [reply_to] if isinstance(reply_to, str) else reply_to

            msg = EmailMultiAlternatives(
                subject=asunto,
                body=texto_plano,
                from_email=remitente,
                to=[destinatario] if isinstance(destinatario, str) else destinatario,
                reply_to=reply_to_list,
                connection=backend
            )
            msg.attach_alternative(html_cuerpo, "text/html")
            msg.send(fail_silently=False)
            logger.info(f"[SMTP] Correo enviado exitosamente a {destinatario}: {asunto}")
            return True
        except Exception as e:
            logger.warning(f"[SMTP] Aviso al enviar correo a {destinatario} ({asunto}): {e}")
            return False

    if asincrono:
        hilo = threading.Thread(target=_ejecutar_envio, daemon=True)
        hilo.start()
        return True
    else:
        return _ejecutar_envio()


def notificar_solicitud_registro_usuario(usuario, nombre_completo, tipo_perfil_nombre):
    """
    Notifica al solicitante que su registro ha sido recibido exitosamente.
    """
    asunto = f"Solicitud de Registro Recibida - Repositorio FCA UABC"
    subtitulo = "Acuse de Recibo Institucional"
    
    contenido_html = f"""
    <p>Estimado(a) <strong>{nombre_completo or usuario.username}</strong>,</p>
    <p>Hemos recibido correctamente tu solicitud de cuenta para el <strong>Repositorio Académico de la Facultad de Contaduría y Administración (FCA - UABC)</strong>.</p>
    
    <div style="background-color: #f1f7f3; border-left: 4px solid #006633; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 0 0 6px 0; font-size: 13px;"><strong>Detalles de tu solicitud:</strong></p>
        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #2d5a3d;">
            <li><strong>Usuario:</strong> {usuario.username}</li>
            <li><strong>Perfil solicitado:</strong> {tipo_perfil_nombre}</li>
            <li><strong>Correo registrado:</strong> {usuario.email}</li>
            <li><strong>Estado actual:</strong> En proceso de revisión institucional</li>
        </ul>
    </div>

    <p>Tu solicitud será revisada por las instancias correspondientes. Tan pronto como tu cuenta sea validada y activada, recibirás una confirmación por este medio con las instrucciones para ingresar.</p>
    """

    texto_plano = (
        f"Estimado(a) {nombre_completo or usuario.username}:\n\n"
        f"Hemos recibido tu solicitud de registro para el Repositorio FCA UABC.\n"
        f"Usuario: {usuario.username}\n"
        f"Perfil: {tipo_perfil_nombre}\n"
        f"Estado: En proceso de revisión\n\n"
        f"Recibirás una notificación cuando tu cuenta sea activada.\n"
        f"Facultad de Contaduría y Administración - UABC"
    )

    return enviar_correo_institucional(usuario.email, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html))


def notificar_solicitud_registro_admins(usuario, nombre_completo, tipo_perfil_nombre):
    """
    Notifica a los Super Administradores activos que hay una nueva solicitud pendiente.
    """
    superadmins = User.objects.filter(is_superuser=True, is_active=True).exclude(email='').values_list('email', flat=True)
    emails = list(filter(None, set(superadmins)))
    if not emails:
        return False

    asunto = f"Nueva Solicitud de Cuenta: {usuario.username} ({tipo_perfil_nombre})"
    subtitulo = "Panel de Administración FCA"

    contenido_html = f"""
    <p>Se ha registrado una nueva solicitud de cuenta que requiere revisión en la plataforma:</p>
    
    <div style="background-color: #fef9ee; border-left: 4px solid #dd971a; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #7c5200;">
            <li><strong>Nombre:</strong> {nombre_completo or usuario.username}</li>
            <li><strong>Usuario:</strong> {usuario.username}</li>
            <li><strong>Perfil:</strong> {tipo_perfil_nombre}</li>
            <li><strong>Correo:</strong> {usuario.email}</li>
        </ul>
    </div>

    <p>Por favor ingresa al <strong>Panel de Usuarios</strong> para evaluar la solicitud y proceder con su aprobación o rechazo.</p>
    """

    texto_plano = (
        f"Nueva Solicitud de Cuenta en Repositorio FCA UABC:\n\n"
        f"Nombre: {nombre_completo or usuario.username}\n"
        f"Usuario: {usuario.username}\n"
        f"Perfil: {tipo_perfil_nombre}\n"
        f"Correo: {usuario.email}\n\n"
        f"Ingresa al panel de usuarios para gestionarla."
    )

    return enviar_correo_institucional(emails, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Ir al Panel de Usuarios", "http://127.0.0.1:8000/panel-usuarios/"))


def notificar_solicitud_tutor_auxiliar(auxiliar_autor, tutor_autor):
    """
    Notifica al profesor tutor que un alumno ha solicitado vincularse como su Auxiliar de Investigación FCA.
    """
    if not tutor_autor or not tutor_autor.correo:
        if tutor_autor and tutor_autor.usuario and tutor_autor.usuario.email:
            destinatario = tutor_autor.usuario.email
        else:
            return False
    else:
        destinatario = tutor_autor.correo

    asunto = f"Solicitud de Vinculación de Auxiliar: {auxiliar_autor.nombre}"
    subtitulo = "Visto Bueno Requerido de Profesor Titular"

    modalidad = getattr(auxiliar_autor, 'modalidad_auxiliar', 'Servicio Social Profesional')
    matricula = getattr(auxiliar_autor, 'matricula_estudiante', 'S/N')

    contenido_html = f"""
    <p>Estimado(a) <strong>{tutor_autor.nombre_con_titulo if hasattr(tutor_autor, 'nombre_con_titulo') else tutor_autor.nombre}</strong>,</p>
    <p>El/La estudiante <strong>{auxiliar_autor.nombre}</strong> ha solicitado registrarse en el Repositorio FCA como tu <strong>Auxiliar de Investigación</strong>.</p>
    
    <div style="background-color: #eff6ff; border-left: 4px solid #0d6efd; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #1e40af;">
            <li><strong>Estudiante / Auxiliar:</strong> {auxiliar_autor.nombre}</li>
            <li><strong>Matrícula / Folio:</strong> {matricula}</li>
            <li><strong>Modalidad:</strong> {modalidad}</li>
            <li><strong>Correo:</strong> {auxiliar_autor.correo or 'N/A'}</li>
        </ul>
    </div>

    <p>Para que la cuenta continúe hacia la activación por Dirección, es necesario que ingreses a <strong>'Mi Panel'</strong> y otorgues tu <strong>Visto Bueno</strong> como profesor responsable.</p>
    """

    texto_plano = (
        f"Estimado(a) {tutor_autor.nombre}:\n\n"
        f"El estudiante {auxiliar_autor.nombre} (Matrícula: {matricula}, Modalidad: {modalidad}) "
        f"ha solicitado registrarse como tu Auxiliar de Investigación en la FCA.\n\n"
        f"Ingresa a 'Mi Panel' en el Repositorio FCA para otorgar tu Visto Bueno."
    )

    return enviar_correo_institucional(destinatario, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Revisar en Mi Panel", "http://127.0.0.1:8000/mi-panel/"))


def notificar_visto_bueno_auxiliar(auxiliar_autor, tutor_autor):
    """
    Notifica al auxiliar que su profesor responsable ha otorgado el Visto Bueno a su vinculación.
    """
    destinatario = auxiliar_autor.correo or (auxiliar_autor.usuario.email if auxiliar_autor.usuario else None)
    if not destinatario:
        return False

    asunto = "¡Visto Bueno Otorgado por tu Profesor Responsable! - Repositorio FCA"
    subtitulo = "Validación Académica Exitosa"

    contenido_html = f"""
    <p>Estimado(a) <strong>{auxiliar_autor.nombre}</strong>,</p>
    <p>Te informamos que tu Profesor(a) Titular Responsable, <strong>{tutor_autor.nombre}</strong>, ha revisado tu solicitud y ha <strong>otorgado su Visto Bueno</strong> a tu vinculación como Auxiliar de Investigación FCA.</p>
    
    <div style="background-color: #f1f7f3; border-left: 4px solid #006633; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 0; font-size: 13px; color: #2d5a3d;">
            <strong>Siguiente paso:</strong> Tu solicitud ha pasado a la fase final de activación por el Super Administrador de la plataforma. Recibirás un aviso en cuanto tu cuenta esté 100% activa.
        </p>
    </div>
    """

    texto_plano = (
        f"Estimado(a) {auxiliar_autor.nombre}:\n\n"
        f"Tu profesor titular {tutor_autor.nombre} ha otorgado el Visto Bueno a tu vinculación.\n"
        f"Tu cuenta pasará ahora a activación final por el Administrador."
    )

    return enviar_correo_institucional(destinatario, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html))


def notificar_aprobacion_cuenta(usuario, tipo_perfil_nombre="Usuario"):
    """
    Notifica al usuario que su cuenta ha sido aprobada y activada por el Super Administrador.
    """
    if not usuario or not usuario.email:
        return False

    asunto = "Tu cuenta ha sido Aprobada y Activada - Repositorio FCA UABC"
    subtitulo = "Bienvenido a la Plataforma Institucional"

    contenido_html = f"""
    <p>Estimado(a) <strong>{usuario.get_full_name() or usuario.username}</strong>,</p>
    <p>Nos complace informarte que tu cuenta para el <strong>Repositorio Académico de la FCA UABC</strong> ha sido revisada y <strong>aprobada exitosamente</strong>.</p>
    
    <div style="background-color: #f1f7f3; border-left: 4px solid #006633; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #2d5a3d;">
            <li><strong>Usuario:</strong> {usuario.username}</li>
            <li><strong>Rol Asignado:</strong> {tipo_perfil_nombre}</li>
            <li><strong>Estatus:</strong> Cuenta Activa y Operativa</li>
        </ul>
    </div>

    <p>Ya puedes iniciar sesión en el repositorio para acceder a tu panel, gestionar tus publicaciones y colaborar en la plataforma académica.</p>
    """

    texto_plano = (
        f"Estimado(a) {usuario.get_full_name() or usuario.username}:\n\n"
        f"Tu cuenta en el Repositorio FCA UABC ha sido aprobada y activada exitosamente.\n"
        f"Usuario: {usuario.username}\n"
        f"Rol: {tipo_perfil_nombre}\n\n"
        f"Ya puedes iniciar sesión en: http://127.0.0.1:8000/login/"
    )

    return enviar_correo_institucional(usuario.email, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Iniciar Sesión", "http://127.0.0.1:8000/login/"))


def notificar_ascenso_superadmin(usuario):
    """
    Notifica al usuario que se le han otorgado privilegios de Super Administrador / Soporte Técnico Pleno.
    """
    if not usuario or not usuario.email:
        return False

    asunto = "Privilegios de Super Administrador Activados - Repositorio FCA"
    subtitulo = "Asignación de Privilegios Ejecutivos"

    contenido_html = f"""
    <p>Estimado(a) <strong>{usuario.get_full_name() or usuario.username}</strong>,</p>
    <p>Se te han otorgado formalmente privilegios de <strong>Super Administrador / Soporte Técnico</strong> en el Repositorio Académico FCA UABC.</p>
    
    <div style="background-color: #fef9ee; border-left: 4px solid #dd971a; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 0 0 6px 0; font-size: 13px; color: #7c5200;"><strong>Nuevas facultades habilitadas:</strong></p>
        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #7c5200;">
            <li>Acceso completo al Panel de Usuarios y Moderación.</li>
            <li>Revisión, aprobación y gestión de documentos académicos.</li>
            <li>Buzón de auditoría institucional y soporte técnico.</li>
            <li>Herramientas de respaldo y depuración de acervos.</li>
        </ul>
    </div>

    <p>Por favor utiliza estas facultades con responsabilidad institucional y apego a las directrices de la FCA.</p>
    """

    texto_plano = (
        f"Estimado(a) {usuario.get_full_name() or usuario.username}:\n\n"
        f"Se te han otorgado privilegios de Super Administrador en el Repositorio FCA UABC.\n"
        f"Ya tienes habilitadas las funciones del panel de control y moderación.\n\n"
        f"Ingresa a la plataforma: http://127.0.0.1:8000/login/"
    )

    return enviar_correo_institucional(usuario.email, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Acceder al Panel de Control", "http://127.0.0.1:8000/panel-usuarios/"))


def notificar_codigo_verificacion_registro(usuario, codigo):
    """
    Envía el código OTP aleatorio de 6 dígitos para autenticar el correo al registrarse.
    Expira en 15 minutos.
    """
    if not usuario or not usuario.email:
        return False

    asunto = f"Código de Verificación: {codigo} - Repositorio FCA UABC"
    subtitulo = "Autenticación de Correo Institucional"

    contenido_html = f"""
    <p>Estimado(a) <strong>{usuario.get_full_name() or usuario.username}</strong>,</p>
    <p>Gracias por iniciar tu registro en el <strong>Repositorio Académico de la FCA UABC</strong>.</p>
    <p>Para autenticar tu correo electrónico y que tu solicitud pase formalmente al panel de revisión de la administración, ingresa el siguiente código de seguridad:</p>
    
    <div style="text-align: center; margin: 30px 0;">
        <div style="font-size: 34px; font-weight: 800; letter-spacing: 10px; color: #006633; background-color: #f1f7f3; padding: 14px 28px; border-radius: 12px; border: 2px dashed #006633; display: inline-block;">
            {codigo}
        </div>
        <p style="margin: 10px 0 0 0; font-size: 12px; color: #dc3545; font-weight: bold;">
            ⏱ Este código expira en 15 minutos
        </p>
    </div>

    <p style="font-size: 13px; color: #6c757d;">
        Si tú no realizaste esta solicitud, por favor ignora este correo. Ninguna cuenta será habilitada sin la verificación previa de este código.
    </p>
    """

    texto_plano = (
        f"Tu código de verificación para el Repositorio FCA UABC es: {codigo}\n\n"
        f"Este código es válido por 15 minutos.\n"
        f"Ingrésalo en la plataforma para autenticar tu correo electrónico."
    )

    return enviar_correo_institucional(usuario.email, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html))


def notificar_codigo_recuperacion_password(usuario, codigo):
    """
    Envía el código de 6 dígitos para restablecer una contraseña olvidada.
    """
    if not usuario or not usuario.email:
        return False

    asunto = f"Código de Recuperación: {codigo} - Repositorio FCA UABC"
    subtitulo = "Restablecimiento de Contraseña"

    contenido_html = f"""
    <p>Estimado(a) <strong>{usuario.get_full_name() or usuario.username}</strong>,</p>
    <p>Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en el <strong>Repositorio Institucional FCA UABC</strong>.</p>
    <p>Utiliza el siguiente código de seguridad temporal para autorizar el cambio de tu contraseña:</p>
    
    <div style="text-align: center; margin: 30px 0;">
        <div style="font-size: 34px; font-weight: 800; letter-spacing: 10px; color: #dd971a; background-color: #fef9ee; padding: 14px 28px; border-radius: 12px; border: 2px dashed #dd971a; display: inline-block;">
            {codigo}
        </div>
        <p style="margin: 10px 0 0 0; font-size: 12px; color: #dc3545; font-weight: bold;">
            ⏱ Este código expira en 15 minutos
        </p>
    </div>

    <p style="font-size: 13px; color: #6c757d;">
        Si no solicitaste este código, te recomendamos revisar la seguridad de tu cuenta o contactar a soporte técnico de la facultad.
    </p>
    """

    texto_plano = (
        f"Tu código para restablecer tu contraseña en el Repositorio FCA UABC es: {codigo}\n\n"
        f"Válido por 15 minutos.\n"
        f"Si no solicitaste el cambio, ignora este mensaje."
    )

    return enviar_correo_institucional(usuario.email, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html))


def notificar_alerta_cambio_password(usuario):
    """
    Alerta de seguridad inmediata cuando la contraseña de una cuenta ha sido modificada.
    """
    if not usuario or not usuario.email:
        return False

    asunto = "Aviso de Seguridad: Contraseña Actualizada - Repositorio FCA"
    subtitulo = "Seguridad de la Cuenta"

    contenido_html = f"""
    <p>Estimado(a) <strong>{usuario.get_full_name() or usuario.username}</strong>,</p>
    <p>Te informamos que la contraseña de tu cuenta en el <strong>Repositorio Institucional FCA UABC</strong> ha sido modificada exitosamente.</p>
    
    <div style="background-color: #f8fafc; border-left: 4px solid #006633; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <ul style="margin: 0; padding-left: 20px; font-size: 13px; color: #334155;">
            <li><strong>Usuario:</strong> {usuario.username}</li>
            <li><strong>Acción:</strong> Cambio de contraseña completado</li>
            <li><strong>Estado:</strong> Sesión segura activa</li>
        </ul>
    </div>

    <p style="font-size: 13px; color: #b91c1c; font-weight: 600;">
        ¿No fuiste tú? Si no reconoces esta acción, por favor comunícate de inmediato con el Área de Ayuda y Soporte Técnico de la FCA para proteger tu cuenta.
    </p>
    """

    texto_plano = (
        f"Estimado(a) {usuario.get_full_name() or usuario.username}:\n\n"
        f"La contraseña de tu cuenta en el Repositorio FCA UABC ha sido actualizada.\n"
        f"Si no realizaste este cambio, contacta de inmediato al soporte técnico institucional."
    )

    return enviar_correo_institucional(usuario.email, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Ir a Soporte", "http://127.0.0.1:8000/soporte/"))


def notificar_obra_aprobada(articulo):
    """
    Notifica al autor que su obra ha sido aprobada y publicada en el catálogo general.
    """
    destinatario = None
    if articulo.subido_por and articulo.subido_por.email:
        destinatario = articulo.subido_por.email
    elif articulo.autor.filter(correo__isnull=False).exists():
        destinatario = articulo.autor.exclude(correo='').values_list('correo', flat=True).first()

    if not destinatario:
        return False

    asunto = f"¡Tu publicación ha sido Aprobada! - Repositorio FCA UABC"
    subtitulo = "Publicación Exitosa en Catálogo"

    año_prod = getattr(articulo, 'año_produccion', None) or getattr(articulo, 'fecha_publicacion', 'N/A')

    contenido_html = f"""
    <p>Estimado(a) autor(a),</p>
    <p>Nos complace informarte que tu publicación académica ha sido <strong>revisada y aprobada exitosamente</strong> por el comité de moderación de la FCA.</p>
    
    <div style="background-color: #f1f7f3; border-left: 4px solid #006633; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <h3 style="margin: 0 0 8px 0; font-size: 15px; color: #006633;">{articulo.titulo}</h3>
        <p style="margin: 0; font-size: 13px; color: #2d5a3d;">
            <strong>Año de publicación:</strong> {año_prod}<br>
            <strong>Estado:</strong> Publicado y visible en el acervo institucional
        </p>
    </div>

    <p>Tu obra ya se encuentra disponible para consulta, descarga y citación por parte de la comunidad académica universitaria e internacional.</p>
    """

    texto_plano = (
        f"¡Enhorabuena! Tu publicación ha sido aprobada:\n\n"
        f"Título: {articulo.titulo}\n"
        f"Año: {año_prod}\n\n"
        f"Ya está disponible en el Repositorio Institucional FCA UABC."
    )

    return enviar_correo_institucional(destinatario, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Ver Catálogo General", "http://127.0.0.1:8000/"))


def notificar_obra_rechazada(articulo, motivo_observaciones):
    """
    Notifica al autor que su obra requiere correcciones o fue devuelta, adjuntando las observaciones.
    """
    destinatario = None
    if articulo.subido_por and articulo.subido_por.email:
        destinatario = articulo.subido_por.email
    elif articulo.autor.filter(correo__isnull=False).exists():
        destinatario = articulo.autor.exclude(correo='').values_list('correo', flat=True).first()

    if not destinatario:
        return False

    asunto = f"Actualización sobre tu publicación: Requiere modificaciones - Repositorio FCA"
    subtitulo = "Observaciones de Moderación Académica"

    obs_formateadas = motivo_observaciones or "Por favor revisa los metadatos o el documento PDF adjunto."

    contenido_html = f"""
    <p>Estimado(a) autor(a),</p>
    <p>El equipo de moderación ha revisado tu publicación <strong>"{articulo.titulo}"</strong> y ha determinado que requiere ajustes antes de ser aprobada.</p>
    
    <div style="background-color: #fff9db; border-left: 4px solid #dd971a; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <h4 style="margin: 0 0 8px 0; font-size: 14px; color: #856404;">Observaciones de Moderación:</h4>
        <div style="font-size: 13px; color: #533f03; white-space: pre-line;">
            {obs_formateadas}
        </div>
    </div>

    <p>Puedes ingresar directamente a la pantalla de edición de tu publicación para corregir los puntos señalados y re-enviarla a revisión.</p>
    """

    texto_plano = (
        f"Tu publicación '{articulo.titulo}' requiere correcciones:\n\n"
        f"Observaciones:\n{obs_formateadas}\n\n"
        f"Ingresa a tu panel para editarla y volverla a enviar: http://127.0.0.1:8000/documento/editar/{articulo.id}/"
    )

    return enviar_correo_institucional(destinatario, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Editar y Corregir Obra", f"http://127.0.0.1:8000/documento/editar/{articulo.id}/"))


def notificar_invitacion_coautoria(invitacion):
    """
    Notifica a un docente que ha sido invitado como coautor en una obra.
    """
    destinatario = None
    autor_inv = invitacion.autor_invitado
    if autor_inv:
        if autor_inv.correo:
            destinatario = autor_inv.correo
        elif autor_inv.usuario and autor_inv.usuario.email:
            destinatario = autor_inv.usuario.email

    if not destinatario:
        return False

    asunto = f"Invitación de Coautoría: '{invitacion.articulo.titulo}' - Repositorio FCA"
    subtitulo = "Colaboración Académica FCA UABC"

    nombre_remitente = invitacion.invitado_por.get_full_name() or invitacion.invitado_por.username if invitacion.invitado_por else "Un colega académico"

    contenido_html = f"""
    <p>Estimado(a) <strong>{autor_inv.nombre}</strong>,</p>
    <p>El(La) investigador(a) <strong>{nombre_remitente}</strong> te ha incluido como coautor(a) en la obra académica:</p>
    
    <div style="background-color: #eff6ff; border-left: 4px solid #0d6efd; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <h3 style="margin: 0 0 6px 0; font-size: 15px; color: #1e40af;">{invitacion.articulo.titulo}</h3>
        <p style="margin: 0; font-size: 12px; color: #3b82f6;">Repositorio Institucional de la FCA UABC</p>
    </div>

    <p>Al aceptar esta invitación, la publicación se vinculará automáticamente a tu perfil académico y aparecerá en tu catálogo oficial.</p>
    """

    texto_plano = (
        f"El investigador {nombre_remitente} te ha invitado como coautor en '{invitacion.articulo.titulo}'.\n\n"
        f"Ingresa a tu módulo de coautorías para aceptar o rechazar la invitación: http://127.0.0.1:8000/coautorias/"
    )

    return enviar_correo_institucional(destinatario, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Revisar en Coautorías", "http://127.0.0.1:8000/coautorias/"))


def notificar_respuesta_coautoria(invitacion):
    """
    Notifica al autor que envió la invitación cuando el colega acepta o rechaza.
    """
    if not invitacion.invitado_por or not invitacion.invitado_por.email:
        return False

    estado_txt = "Aceptada" if invitacion.estado == 'aceptada' else "Rechazada"
    color_border = "#006633" if invitacion.estado == 'aceptada' else "#dc3545"
    subtitulo = "Confirmación de Coautoría"

    asunto = f"Invitación de Coautoría {estado_txt}: '{invitacion.articulo.titulo}'"

    nombre_invitado = invitacion.autor_invitado.nombre if invitacion.autor_invitado else "El colega invitado"

    contenido_html = f"""
    <p>Estimado(a) <strong>{invitacion.invitado_por.get_full_name() or invitacion.invitado_por.username}</strong>,</p>
    <p>Te informamos que <strong>{nombre_invitado}</strong> ha <strong>{estado_txt.lower()}</strong> la invitación de coautoría para la obra:</p>
    
    <div style="background-color: #f8fafc; border-left: 4px solid {color_border}; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <h4 style="margin: 0; font-size: 14px; color: #1e293b;">{invitacion.articulo.titulo}</h4>
    </div>
    """

    texto_plano = (
        f"{nombre_invitado} ha {estado_txt.lower()} tu invitación de coautoría para '{invitacion.articulo.titulo}'.\n\n"
        f"Consulta tus obras en Mi Panel: http://127.0.0.1:8000/mi-panel/"
    )

    return enviar_correo_institucional(invitacion.invitado_por.email, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Ver Mi Panel", "http://127.0.0.1:8000/mi-panel/"))


def notificar_nuevo_mensaje_interno(mensaje):
    """
    Notifica al destinatario que tiene un nuevo mensaje privado en la plataforma.
    """
    destinatario = None
    if mensaje.destinatario:
        if mensaje.destinatario.correo:
            destinatario = mensaje.destinatario.correo
        elif mensaje.destinatario.usuario and mensaje.destinatario.usuario.email:
            destinatario = mensaje.destinatario.usuario.email

    if not destinatario:
        return False

    remitente_nombre = mensaje.remitente.get_full_name() or mensaje.remitente.username if mensaje.remitente else "Colega Académico"
    asunto = f"Nuevo Mensaje de {remitente_nombre} - Repositorio FCA"
    subtitulo = "Bandeja de Mensajería Interna"

    contenido_html = f"""
    <p>Estimado(a) colega,</p>
    <p>Has recibido un nuevo mensaje institucional de <strong>{remitente_nombre}</strong>:</p>
    
    <div style="background-color: #f8fafc; border-left: 4px solid #006633; padding: 14px 18px; margin: 20px 0; border-radius: 4px;">
        <p style="margin: 0 0 6px 0; font-size: 14px; font-weight: bold; color: #006633;">{mensaje.asunto}</p>
        <p style="margin: 0; font-size: 13px; color: #475569; font-style: italic;">
            "{mensaje.cuerpo[:160]}{'...' if len(mensaje.cuerpo) > 160 else ''}"
        </p>
    </div>

    <p>Ingresa a tu bandeja de mensajería para leer el mensaje completo y responder.</p>
    """

    texto_plano = (
        f"Has recibido un mensaje de {remitente_nombre} en el Repositorio FCA:\n\n"
        f"Asunto: {mensaje.asunto}\n\n"
        f"Ingresa para responder: http://127.0.0.1:8000/mensajeria/"
    )

    return enviar_correo_institucional(destinatario, asunto, texto_plano, generar_html_base(asunto, subtitulo, contenido_html, "Ir a Mensajería", "http://127.0.0.1:8000/mensajeria/"))



def notificar_nuevo_mensaje_contacto_soporte(contacto):
    """
    Envía una alerta inmediata al buzón del equipo de soporte con los datos
    y el mensaje de la consulta recibida desde /contacto/.
    Permite a soporte responder directamente al solicitante gracias al encabezado Reply-To.
    """
    config = obtener_config_envio_correo()
    destinatario = (config.soporte_email or 'soporte.fca@uabc.edu.mx').strip() if config else 'soporte.fca@uabc.edu.mx'
    
    asunto = f"[Contacto FCA - Folio {contacto.folio}] {contacto.asunto}"
    subtitulo = "Nueva consulta recibida desde el portal institucional"

    fecha_fmt = contacto.fecha_creacion.strftime('%d/%m/%Y a las %H:%M hrs') if hasattr(contacto, 'fecha_creacion') and contacto.fecha_creacion else "Hoy"

    contenido_html = f"""
    <p>Se ha recibido una nueva solicitud de contacto a través del portal institucional del <strong>Repositorio FCA</strong>:</p>

    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px 20px; margin: 20px 0; box-shadow: 0 2px 6px rgba(0,0,0,0.04);">
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr>
                <td style="padding: 6px 0; color: #64748b; width: 140px;"><strong>Folio:</strong></td>
                <td style="padding: 6px 0;"><span style="background-color: #dd971a; color: #ffffff; padding: 3px 8px; border-radius: 4px; font-weight: bold; font-size: 12px;">{contacto.folio}</span></td>
            </tr>
            <tr>
                <td style="padding: 6px 0; color: #64748b;"><strong>Nombre:</strong></td>
                <td style="padding: 6px 0; color: #1e293b; font-weight: bold;">{contacto.nombre}</td>
            </tr>
            <tr>
                <td style="padding: 6px 0; color: #64748b;"><strong>Correo solicitante:</strong></td>
                <td style="padding: 6px 0;"><a href="mailto:{contacto.email}" style="color: #006633; font-weight: bold; text-decoration: none;">{contacto.email}</a></td>
            </tr>
            <tr>
                <td style="padding: 6px 0; color: #64748b;"><strong>Teléfono:</strong></td>
                <td style="padding: 6px 0; color: #1e293b;">{contacto.telefono or 'No proporcionado'}</td>
            </tr>
            <tr>
                <td style="padding: 6px 0; color: #64748b;"><strong>Institución/Empresa:</strong></td>
                <td style="padding: 6px 0; color: #1e293b;">{contacto.organizacion or 'No especificada'}</td>
            </tr>
            <tr>
                <td style="padding: 6px 0; color: #64748b;"><strong>Asunto:</strong></td>
                <td style="padding: 6px 0; color: #1e293b; font-weight: bold;">{contacto.asunto}</td>
            </tr>
            <tr>
                <td style="padding: 6px 0; color: #64748b;"><strong>Fecha:</strong></td>
                <td style="padding: 6px 0; color: #64748b;">{fecha_fmt}</td>
            </tr>
        </table>
    </div>

    <div style="margin: 20px 0;">
        <div style="font-size: 13px; font-weight: bold; text-transform: uppercase; color: #006633; margin-bottom: 8px;">
            Mensaje o Pregunta del Solicitante:
        </div>
        <div style="background-color: #f8fafc; border-left: 4px solid #006633; padding: 16px 20px; border-radius: 4px; font-size: 14px; color: #334155; line-height: 1.6; white-space: pre-wrap;">{contacto.mensaje}</div>
    </div>

    <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 12px 16px; margin: 20px 0; font-size: 13px; color: #166534;">
        💡 <strong>Respuesta rápida:</strong> Puedes hacer clic directamente en <em>"Responder"</em> en tu cliente de correo para escribirle de inmediato a <strong>{contacto.nombre}</strong> ({contacto.email}).
    </div>
    """

    texto_plano = (
        f"NUEVO MENSAJE DE CONTACTO FCA\n"
        f"Folio: {contacto.folio}\n"
        f"Nombre: {contacto.nombre}\n"
        f"Correo: {contacto.email}\n"
        f"Teléfono: {contacto.telefono or 'N/A'}\n"
        f"Organización: {contacto.organizacion or 'N/A'}\n"
        f"Asunto: {contacto.asunto}\n\n"
        f"Mensaje:\n{contacto.mensaje}\n"
    )

    url_panel = "http://127.0.0.1:8000/configuracion-soporte/#seccion-contacto-web"
    html_final = generar_html_base(asunto, subtitulo, contenido_html, "Ver en Panel de Soporte", url_panel)
    return enviar_correo_institucional(destinatario, asunto, texto_plano, html_final, reply_to=contacto.email)


def notificar_acuse_recibo_contacto_usuario(contacto):
    """
    Envía un acuse de recibo formal al solicitante confirmando que su consulta
    ha sido registrada con éxito y proporcionándole su folio de seguimiento.
    """
    config = obtener_config_envio_correo()
    soporte_email = (config.soporte_email or 'soporte.fca@uabc.edu.mx').strip() if config else 'soporte.fca@uabc.edu.mx'
    tiempo_resp = (config.soporte_tiempo_respuesta or 'Menos de 24 horas hábiles').strip() if config else 'Menos de 24 horas hábiles'

    asunto = f"Acuse de Recibo: Tu consulta en el Repositorio FCA [{contacto.folio}]"
    subtitulo = "Confirmación de Recepción &bull; Facultad de Contaduría y Administración"

    contenido_html = f"""
    <p>Estimado(a) <strong>{contacto.nombre}</strong>,</p>
    <p>Hemos recibido correctamente tu mensaje a través del formulario de contacto del <strong>Repositorio Institucional de la Facultad de Contaduría y Administración (UABC)</strong>.</p>

    <div style="text-align: center; margin: 25px 0;">
        <div style="display: inline-block; background-color: #f8fafc; border: 2px dashed #006633; border-radius: 8px; padding: 14px 28px;">
            <div style="font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 1.5px; color: #64748b; margin-bottom: 4px;">Tu Folio de Atención</div>
            <div style="font-size: 20px; font-weight: 800; color: #006633; letter-spacing: 1px;">{contacto.folio}</div>
        </div>
    </div>

    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px 20px; margin: 20px 0;">
        <div style="font-size: 13px; font-weight: bold; text-transform: uppercase; color: #dd971a; margin-bottom: 10px;">Resumen de tu solicitud:</div>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
            <tr>
                <td style="padding: 5px 0; color: #64748b; width: 120px;"><strong>Asunto:</strong></td>
                <td style="padding: 5px 0; color: #1e293b;">{contacto.asunto}</td>
            </tr>
            <tr>
                <td style="padding: 5px 0; color: #64748b;"><strong>Mensaje:</strong></td>
                <td style="padding: 5px 0; color: #334155; font-style: italic;">"{contacto.mensaje[:220]}{'...' if len(contacto.mensaje) > 220 else ''}"</td>
            </tr>
            <tr>
                <td style="padding: 5px 0; color: #64748b;"><strong>Tiempo de respuesta:</strong></td>
                <td style="padding: 5px 0; color: #166534; font-weight: bold;">{tiempo_resp}</td>
            </tr>
        </table>
    </div>

    <p>Nuestro equipo de soporte institucional revisará tu solicitud a la brevedad y te responderá a esta misma dirección de correo (<strong>{contacto.email}</strong>).</p>

    <p style="font-size: 13px; color: #64748b; margin-top: 25px;">
        Si requieres aportar información adicional o dar seguimiento, puedes responder directamente a este correo o escribir a <a href="mailto:{soporte_email}" style="color: #006633; font-weight: bold;">{soporte_email}</a> citando tu número de folio.
    </p>
    """

    texto_plano = (
        f"Hola {contacto.nombre},\n\n"
        f"Hemos recibido tu mensaje en el Repositorio Institucional FCA (UABC).\n\n"
        f"Folio de atención: {contacto.folio}\n"
        f"Asunto: {contacto.asunto}\n"
        f"Tiempo estimado de respuesta: {tiempo_resp}\n\n"
        f"Te responderemos a la brevedad a través de este correo.\n"
    )

    html_final = generar_html_base(asunto, subtitulo, contenido_html)
    return enviar_correo_institucional(contacto.email, asunto, texto_plano, html_final, reply_to=soporte_email)


def notificar_resolucion_contacto_usuario(contacto, mensaje_opcional=None):
    """
    Envía un correo formal al solicitante informándole que su consulta ha sido
    resuelta por el equipo de soporte, incluyendo la respuesta oficial de soporte
    si se proporcionó.
    """
    config = obtener_config_envio_correo()
    soporte_email = (config.soporte_email or 'soporte.fca@uabc.edu.mx').strip() if config else 'soporte.fca@uabc.edu.mx'

    asunto = f"Consulta Resuelta: [Folio {contacto.folio}] {contacto.asunto}"
    subtitulo = "Soporte Institucional &bull; Facultad de Contaduría y Administración"

    respuesta_final = (mensaje_opcional or contacto.respuesta_soporte or '').strip()

    bloque_respuesta = ""
    if respuesta_final:
        bloque_respuesta = f"""
        <div style="background-color: #f0fdf4; border: 1px solid #bbf7d0; border-left: 5px solid #16a34a; border-radius: 8px; padding: 18px 20px; margin: 25px 0;">
            <div style="font-size: 13px; font-weight: bold; text-transform: uppercase; color: #15803d; margin-bottom: 8px;">
                Respuesta del Equipo de Soporte FCA:
            </div>
            <div style="font-size: 14px; color: #166534; line-height: 1.6; white-space: pre-wrap;">{respuesta_final}</div>
        </div>
        """

    contenido_html = f"""
    <p>Estimado(a) <strong>{contacto.nombre}</strong>,</p>
    <p>Te informamos que tu consulta con folio institucional <strong>{contacto.folio}</strong> ha sido atendida y marcada como <strong>Resuelta</strong> por el equipo de Soporte de la Facultad de Contaduría y Administración (UABC).</p>

    <div style="text-align: center; margin: 25px 0;">
        <div style="display: inline-block; background-color: #f0fdf4; border: 2px solid #16a34a; border-radius: 8px; padding: 12px 26px;">
            <div style="font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 1.5px; color: #15803d; margin-bottom: 3px;">Estado del Ticket</div>
            <div style="font-size: 18px; font-weight: 800; color: #166534; letter-spacing: 1px;">✓ RESUELTO &bull; {contacto.folio}</div>
        </div>
    </div>

    {bloque_respuesta}

    <div style="background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px 20px; margin: 20px 0;">
        <div style="font-size: 13px; font-weight: bold; text-transform: uppercase; color: #64748b; margin-bottom: 8px;">Resumen de tu solicitud original:</div>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
            <tr>
                <td style="padding: 4px 0; color: #64748b; width: 110px;"><strong>Asunto:</strong></td>
                <td style="padding: 4px 0; color: #1e293b;">{contacto.asunto}</td>
            </tr>
            <tr>
                <td style="padding: 4px 0; color: #64748b;"><strong>Mensaje:</strong></td>
                <td style="padding: 4px 0; color: #475569; font-style: italic;">"{contacto.mensaje}"</td>
            </tr>
        </table>
    </div>

    <p style="font-size: 13px; color: #64748b; margin-top: 25px;">
        Agradecemos tu comunicación. Si consideras que tu solicitud aún requiere asistencia adicional o tienes nuevas dudas, puedes responder directamente a este correo o escribir a <a href="mailto:{soporte_email}" style="color: #006633; font-weight: bold;">{soporte_email}</a> citando tu número de folio.
    </p>
    """

    texto_plano = (
        f"Hola {contacto.nombre},\n\n"
        f"Tu consulta con folio institucional {contacto.folio} ha sido atendida y marcada como RESUELTA por el equipo de Soporte FCA.\n\n"
        f"Asunto: {contacto.asunto}\n"
    )
    if respuesta_final:
        texto_plano += f"\nRespuesta de soporte:\n{respuesta_final}\n\n"
    texto_plano += f"Si requieres más información, responde a este correo o escribe a {soporte_email}.\n"

    html_final = generar_html_base(asunto, subtitulo, contenido_html)
    return enviar_correo_institucional(contacto.email, asunto, texto_plano, html_final, reply_to=soporte_email)
