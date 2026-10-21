from django.utils import timezone
from .models import Autor, InvitacionCoautoria, MensajeInterno

def obtener_tema_rol(user):
    """
    Retorna la paleta de colores institucional y metadatos visuales según el rol del usuario:
    - Verde Institucional UABC (#006633, acento dorado #dd971a): Docentes UABC y Super Administradores
    - Azul Celeste (#0284c7, acento cyan #38bdf8): Colaboradores Externos
    - Morado Académico (#6f42c1, acento lavanda #c084fc): Investigadores Independientes
    - Azul Rey (#0d6efd, acento azul cielo #60a5fa): Personal Administrativo y Auxiliares de Investigación FCA
    """
    if not user or not user.is_authenticated:
        return {
            'clave': 'verde',
            'nombre_rol': 'Docente / Investigador UABC',
            'primary': '#006633',
            'primary_dark': '#004d26',
            'primary_light': '#008040',
            'primary_rgb': '0, 102, 51',
            'accent': '#dd971a',
            'accent_dark': '#b37700',
            'accent_soft': 'rgba(221, 151, 26, 0.2)',
            'tag_color': '#a3e9c0',
            'tag_text': 'MENÚ FCA',
            'badge_style': 'background-color: #006633; color: #ffffff;',
            'badge_text': 'Docente UABC',
            'badge_icon': 'fas fa-chalkboard-teacher',
            'topbar_badge': 'bg-success',
        }

    # 1. Super Administradores: Verde Institucional UABC
    if user.is_superuser:
        return {
            'clave': 'verde',
            'nombre_rol': 'Super Administrador',
            'primary': '#006633',
            'primary_dark': '#004d26',
            'primary_light': '#008040',
            'primary_rgb': '0, 102, 51',
            'accent': '#dd971a',
            'accent_dark': '#b37700',
            'accent_soft': 'rgba(221, 151, 26, 0.2)',
            'tag_color': '#a3e9c0',
            'tag_text': 'SUPER ADMIN',
            'badge_style': 'background-color: #006633; color: #ffffff;',
            'badge_text': 'Super Administrador',
            'badge_icon': 'fas fa-shield-alt',
            'topbar_badge': 'bg-success',
        }

    autor = getattr(user, 'autor', None)

    # 2. Con perfil de Autor
    if autor:
        inst = (autor.institucion_origen or '').lower()
        # 2.1 Soporte Técnico / Administración (Modo Lector / Pendiente de ascenso a Superadmin)
        if getattr(autor, 'es_soporte', False) or autor.rol_facultad == 'SOPORTE':
            return {
                'clave': 'soporte',
                'nombre_rol': 'Soporte Técnico (Modo Lector)',
                'primary': '#1e293b',
                'primary_dark': '#0f172a',
                'primary_light': '#334155',
                'primary_rgb': '30, 41, 59',
                'accent': '#dd971a',
                'accent_dark': '#b37700',
                'accent_soft': 'rgba(221, 151, 26, 0.25)',
                'tag_color': '#fed7aa',
                'tag_text': 'SOPORTE FCA',
                'badge_style': 'background-color: #1e293b; color: #ffffff; border: 1px solid #dd971a;',
                'badge_text': 'Soporte Técnico (Modo Lector)',
                'badge_icon': 'fas fa-headset',
                'topbar_badge': 'bg-dark text-warning',
            }

        # 2.2 Operador Técnico / Depurador de Contenidos (Teal / Cian de Producción y Digitalización)
        if getattr(autor, 'es_operador_tecnico', False) or autor.rol_facultad == 'DEP_TEC':
            return {
                'clave': 'teal',
                'nombre_rol': 'Operador Técnico / Depurador de Contenidos',
                'primary': '#0891b2',
                'primary_dark': '#0e7490',
                'primary_light': '#06b6d4',
                'primary_rgb': '8, 145, 178',
                'accent': '#22d3ee',
                'accent_dark': '#0891b2',
                'accent_soft': 'rgba(34, 211, 238, 0.25)',
                'tag_color': '#cffafe',
                'tag_text': 'DEPURADOR FCA',
                'badge_style': 'background-color: #0891b2; color: #ffffff;',
                'badge_text': 'Operador Técnico FCA',
                'badge_icon': 'fas fa-tools',
                'topbar_badge': 'bg-info text-white',
            }

        # 2.3 Auxiliar de Investigación FCA (Azul Rey)
        if getattr(autor, 'es_auxiliar', False) or autor.rol_facultad == 'AUX_INV':
            return {
                'clave': 'azul',
                'nombre_rol': 'Auxiliar de Investigación FCA',
                'primary': '#0d6efd',
                'primary_dark': '#0a58ca',
                'primary_light': '#3b82f6',
                'primary_rgb': '13, 110, 253',
                'accent': '#60a5fa',
                'accent_dark': '#2563eb',
                'accent_soft': 'rgba(96, 165, 250, 0.25)',
                'tag_color': '#bfdbfe',
                'tag_text': 'AUXILIAR FCA',
                'badge_style': 'background-color: #0d6efd; color: #ffffff;',
                'badge_text': 'Auxiliar de Investigación FCA',
                'badge_icon': 'fas fa-hands-helping',
                'topbar_badge': 'bg-primary text-white',
            }

        # 2.4 Investigador Independiente (Morado)
        if autor.rol_facultad == 'INV_IND' or 'independiente' in inst:
            return {
                'clave': 'morado',
                'nombre_rol': 'Investigador Independiente',
                'primary': '#6f42c1',
                'primary_dark': '#59359a',
                'primary_light': '#8b5cf6',
                'primary_rgb': '111, 66, 193',
                'accent': '#c084fc',
                'accent_dark': '#7e22ce',
                'accent_soft': 'rgba(192, 132, 252, 0.25)',
                'tag_color': '#e9d5ff',
                'tag_text': 'INDEPENDIENTE',
                'badge_style': 'background-color: #6f42c1; color: #ffffff;',
                'badge_text': 'Investigador Independiente',
                'badge_icon': 'fas fa-user-graduate',
                'topbar_badge': 'bg-purple text-white',
            }

        # 2.5 Colaborador Externo (Celeste)
        if autor.es_externo or autor.rol_facultad == 'EXT':
            return {
                'clave': 'celeste',
                'nombre_rol': 'Colaborador Externo',
                'primary': '#0284c7',
                'primary_dark': '#0369a1',
                'primary_light': '#38bdf8',
                'primary_rgb': '2, 132, 199',
                'accent': '#38bdf8',
                'accent_dark': '#0284c7',
                'accent_soft': 'rgba(56, 189, 248, 0.25)',
                'tag_color': '#bae6fd',
                'tag_text': 'EXTERNO FCA',
                'badge_style': 'background-color: #0284c7; color: #ffffff;',
                'badge_text': 'Colaborador Externo',
                'badge_icon': 'fas fa-globe-americas',
                'topbar_badge': 'bg-info text-white',
            }

        # 2.6 Docente UABC (Verde Institucional)
        if autor.es_profesor or autor.rol_facultad in ['TC', 'ASIG', 'INV', 'OTRO']:
            rol_docente = autor.get_rol_facultad_display() if hasattr(autor, 'get_rol_facultad_display') else 'Docente UABC'
            return {
                'clave': 'verde',
                'nombre_rol': 'Docente UABC',
                'primary': '#006633',
                'primary_dark': '#004d26',
                'primary_light': '#008040',
                'primary_rgb': '0, 102, 51',
                'accent': '#dd971a',
                'accent_dark': '#b37700',
                'accent_soft': 'rgba(221, 151, 26, 0.2)',
                'tag_color': '#a3e9c0',
                'tag_text': 'DOCENTE UABC',
                'badge_style': 'background-color: #006633; color: #ffffff;',
                'badge_text': rol_docente or 'Docente UABC',
                'badge_icon': 'fas fa-chalkboard-teacher',
                'topbar_badge': 'bg-success',
            }

        # Personal Administrativo general (Azul Marino / Gris)
        nombre_display = 'Personal Administrativo'
        return {
            'clave': 'azul',
            'nombre_rol': nombre_display,
            'primary': '#0d6efd',
            'primary_dark': '#0a58ca',
            'primary_light': '#3b82f6',
            'primary_rgb': '13, 110, 253',
            'accent': '#60a5fa',
            'accent_dark': '#2563eb',
            'accent_soft': 'rgba(96, 165, 250, 0.25)',
            'tag_color': '#bfdbfe',
            'tag_text': 'ADMINISTRATIVO',
            'badge_style': 'background-color: #0d6efd; color: #ffffff;',
            'badge_text': nombre_display,
            'badge_icon': 'fas fa-user-tie',
            'topbar_badge': 'bg-primary text-white',
        }

    # 3. Usuario sin autor (no superuser) -> Soporte Técnico básico o Administrativo
    return {
        'clave': 'soporte',
        'nombre_rol': 'Soporte Técnico (Modo Lector)',
        'primary': '#1e293b',
        'primary_dark': '#0f172a',
        'primary_light': '#334155',
        'primary_rgb': '30, 41, 59',
        'accent': '#dd971a',
        'accent_dark': '#b37700',
        'accent_soft': 'rgba(221, 151, 26, 0.25)',
        'tag_color': '#fed7aa',
        'tag_text': 'SOPORTE FCA',
        'badge_style': 'background-color: #1e293b; color: #ffffff; border: 1px solid #dd971a;',
        'badge_text': 'Soporte Técnico (Modo Lector)',
        'badge_icon': 'fas fa-headset',
        'topbar_badge': 'bg-dark text-warning',
    }


def notificaciones_institucionales(request):
    """
    Context processor global para la barra lateral y cabeceras institucionales.
    Proporciona conteos en tiempo real y paleta temática por rol:
    - tema_rol: Paleta de colores y estilos visuales según el tipo de usuario
    - invitaciones_pendientes_count: Invitaciones de coautoría pendientes
    - mensajes_no_leidos_count: Mensajes académicos no leídos
    - soporte_pendientes_count: Consultas a soporte institucional
    - cumpleaneros_hoy: Docentes que cumplen años hoy
    """
    u = getattr(request, 'user', None)
    es_super_principal = False
    if u and u.is_authenticated and u.is_superuser:
        if u.username.lower() == 'yaele' or u.id == 1:
            es_super_principal = True
        else:
            try:
                from django.contrib.auth.models import User
                primer = User.objects.filter(is_superuser=True).order_by('id').first()
                if primer and u.id == primer.id:
                    es_super_principal = True
            except Exception:
                pass

    context = {
        'invitaciones_pendientes_count': 0,
        'mensajes_no_leidos_count': 0,
        'soporte_pendientes_count': 0,
        'auxiliares_pendientes_count': 0,
        'cumpleaneros_hoy': False,
        'tema_rol': obtener_tema_rol(getattr(request, 'user', None)),
        'es_superadmin_principal': es_super_principal,
    }

    # Docentes de cumpleaños hoy
    try:
        hoy = timezone.localdate()
        context['cumpleaneros_hoy'] = Autor.objects.filter(
            fecha_nacimiento__month=hoy.month,
            fecha_nacimiento__day=hoy.day
        ).exists()
    except Exception:
        pass

    if not request.user.is_authenticated:
        return context

    # 1. Superusuarios: Solicitudes de soporte enviadas por docentes pendientes de atención
    if request.user.is_superuser:
        try:
            context['soporte_pendientes_count'] = MensajeInterno.objects.filter(
                es_soporte=True,
                remitente__is_superuser=False,
                leido=False
            ).count()
        except Exception:
            pass

    # 2. Docente con perfil de Autor
    if hasattr(request.user, 'autor') and request.user.autor:
        mi_autor = request.user.autor
        try:
            if mi_autor.es_auxiliar and mi_autor.profesor_tutor and mi_autor.aprobado_por_tutor:
                from .models import InvitacionCoautoria
                context['invitaciones_pendientes_count'] = InvitacionCoautoria.objects.filter(
                    autor_invitado__in=[mi_autor, mi_autor.profesor_tutor],
                    estado='pendiente'
                ).count()
                context['profesor_tutor'] = mi_autor.profesor_tutor
            else:
                context['invitaciones_pendientes_count'] = mi_autor.invitaciones_recibidas.filter(
                    estado='pendiente'
                ).count()
        except Exception:
            pass

        try:
            # Mensajes recibidos no leídos (estrictamente entre colegas dirigidos a este docente)
            context['mensajes_no_leidos_count'] = mi_autor.mensajes_academicos_recibidos.filter(
                es_soporte=False,
                leido=False
            ).count()
        except Exception:
            pass

        # Para docentes normales, soporte_pendientes_count indica si Soporte les respondió y no lo han leído
        if not request.user.is_superuser:
            try:
                context['soporte_pendientes_count'] = mi_autor.mensajes_academicos_recibidos.filter(
                    es_soporte=True,
                    leido=False
                ).count()
            except Exception:
                pass

        # Para docentes tutores: Auxiliares de investigación pendientes de su Visto Bueno
        if mi_autor.es_profesor and not mi_autor.es_externo:
            try:
                context['auxiliares_pendientes_count'] = mi_autor.auxiliares_asignados.filter(
                    aprobado_por_tutor=False,
                    estado_cuenta='pendiente'
                ).count()
            except Exception:
                pass
    else:
        # Si el usuario no tiene autor (como la cuenta del Super Admin principal Yaele),
        # no tiene buzón personal de mensajes entre colegas, por lo que el conteo es 0.
        context['mensajes_no_leidos_count'] = 0

    return context
