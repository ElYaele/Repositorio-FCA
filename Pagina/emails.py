import os
import logging
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


def enviar_correo_institucional(destinatario, asunto, texto_plano, html_cuerpo):
    """
    Envía un correo electrónico multipart (texto + HTML) de manera segura.
    Si el servidor SMTP no está disponible o falla, registra el evento sin interrumpir la ejecución.
    """
    if not destinatario:
        return False

    remitente = getattr(settings, 'DEFAULT_FROM_EMAIL', 'Repositorio FCA UABC <notificaciones.fca.uabc@gmail.com>')

    try:
        # Fallback a console backend si no hay contraseña SMTP configurada
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')
        if not password and getattr(settings, 'EMAIL_BACKEND', '') == 'django.core.mail.backends.smtp.EmailBackend':
            from django.core.mail.backends.console import EmailBackend as ConsoleBackend
            backend = ConsoleBackend()
        else:
            backend = None

        msg = EmailMultiAlternatives(
            subject=asunto,
            body=texto_plano,
            from_email=remitente,
            to=[destinatario] if isinstance(destinatario, str) else destinatario,
            connection=backend
        )
        msg.attach_alternative(html_cuerpo, "text/html")
        msg.send(fail_silently=False)
        logger.info(f"Correo enviado exitosamente a {destinatario}: {asunto}")
        return True
    except Exception as e:
        logger.warning(f"Aviso al enviar correo a {destinatario} ({asunto}): {e}")
        return False


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
        ¿No fuiste tú? Si no reconoces esta acción, por favor comunícate de inmediato con la Mesa de Ayuda y Soporte Técnico de la FCA para proteger tu cuenta.
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

