"""
====================================================================================================
SISTEMA DE REPOSITORIO ACADÉMICO INSTITUCIONAL (FCA - UABC)
Módulo: Pagina/backends.py
Descripción: Backend Personalizado de Autenticación Institucional Dual y Desbloqueo Automático.
Autor: Facultad de Contaduría y Administración - Campus Tijuana
====================================================================================================
Este módulo sobreescribe el comportamiento estándar de autenticación de Django para proporcionar:
1. Autenticación Dual e Insensible a Mayúsculas: Permite a los docentes y alumnos ingresar indistintamente
   con su correo institucional (@uabc.edu.mx / @alumnos.uabc.edu.mx) o con su nombre de usuario (username).
2. Reactivación Automática de Cuentas Temporales: Verifica si una cuenta sujeta a suspensión temporal
   ha superado la fecha límite estipulada; si es así, levanta la suspensión en tiempo real durante
   el intento de login sin intervención manual del administrador.
====================================================================================================
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone


class EmailOrUsernameModelBackend(ModelBackend):
    """
    Backend de autenticación flexible que permite iniciar sesión usando
    indistintamente el nombre de usuario (username) o el correo electrónico (email).
    Además, gestiona el desbloqueo automático de cuentas con suspensión por tiempo definido.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        """
        Valida las credenciales proporcionadas contra los registros de la base de datos.

        Parámetros:
            request (HttpRequest): Objeto de solicitud HTTP.
            username (str): Identificador ingresado (puede ser correo o nombre de usuario).
            password (str): Contraseña en texto plano a verificar mediante hash criptográfico (PBKDF2/SHA256).
            **kwargs: Parámetros opcionales adicionales (ej. 'email').

        Retorna:
            User: Instancia del modelo de usuario si las credenciales son válidas; de lo contrario, None.
        """
        if username is None:
            username = kwargs.get('email')
        if username is None or password is None:
            return None

        # Limpiar espacios en blanco periféricos
        username = str(username).strip()

        try:
            # Buscar usuario por nombre de usuario o por correo (insensible a mayúsculas/minúsculas)
            usuario = User.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).first()

            if not usuario:
                return None

            # Si el usuario tiene suspensión por tiempo definido y ya expiró, reactivarlo automáticamente
            if hasattr(usuario, 'autor') and usuario.autor:
                autor = usuario.autor
                if autor.estado_cuenta == 'suspendida' and autor.fecha_fin_suspension:
                    if timezone.now() >= autor.fecha_fin_suspension:
                        usuario.is_active = True
                        usuario.save()
                        autor.estado_cuenta = 'activa'
                        autor.motivo_suspension = ''
                        autor.fecha_fin_suspension = None
                        autor.fecha_suspension = None
                        autor.suspendido_por = None
                        autor.save()

            # Verificación del hash de contraseña con sales criptográficas
            if usuario.check_password(password):
                return usuario
        except Exception:
            return None

        return None
