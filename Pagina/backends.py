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
        if username is None:
            username = kwargs.get('email')
        if username is None or password is None:
            return None

        # Limpiar espacios
        username = str(username).strip()

        try:
            # Buscar usuario por nombre de usuario o por correo (case-insensitive)
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

            if usuario.check_password(password):
                return usuario
        except Exception:
            return None

        return None
