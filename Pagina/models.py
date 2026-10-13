from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

GENERO_OPCIONES = [
    ('F', 'Femenino'),
    ('M', 'Masculino'),
    ('NB', 'No binario'),
    ('O', 'Otro / Prefiero describirme'),
    ('NE', 'Prefiero no especificar'),
]

ROL_DOCENTE_OPCIONES = [
    ('PTC', 'Profesor de Tiempo Completo'),
    ('ASIG', 'Profesor de Asignatura'),
    ('INV', 'Investigador / SNII'),
    ('COORD', 'Coordinador Académico'),
    ('EXT', 'Colaborador Externo'),
    ('OTRO', 'Docente / Investigador'),
]


class RegistroAuditoria(models.Model):
    """Modelo para registrar las acciones y cambios realizados por los administradores (Buzón de Auditoría)."""
    admin_usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='acciones_auditoria')
    accion = models.CharField(max_length=255, verbose_name="Acción realizada")
    detalle = models.TextField(blank=True, null=True, verbose_name="Detalles del cambio")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Fecha y Hora")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at.strftime('%d/%m/%Y %H:%M')}] {self.admin_usuario} - {self.accion}"


class Nombramiento(models.Model):
    """Modelo auxiliar para soportar múltiples cargos o nombramientos académicos por autor."""
    autor = models.ForeignKey('Autor', on_delete=models.CASCADE, related_name='nombramientos')
    rol = models.CharField(max_length=10, choices=ROL_DOCENTE_OPCIONES, verbose_name="Cargo o Nivel")

    def get_rol_display_text(self):
        return dict(ROL_DOCENTE_OPCIONES).get(self.rol, self.rol)

    def __str__(self):
        return f"{self.autor.nombre} - {self.get_rol_display_text()}"


class Universidad(models.Model):
    """Catálogo global de universidades e instituciones para autores externos."""
    nombre = models.CharField(max_length=255, unique=True, verbose_name="Nombre de la Universidad o Institución")
    siglas = models.CharField(max_length=50, verbose_name="Siglas Oficiales")

    class Meta:
        verbose_name = "Universidad"
        verbose_name_plural = "Universidades"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.siglas})"


class Autor(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='autor')
    nombre = models.CharField(max_length=150)
    numero_empleado = models.CharField(max_length=50, blank=True, null=True)
    es_profesor = models.BooleanField(default=False, verbose_name="¿Es profesor/investigador?")
    correo = models.EmailField(blank=True, null=True)

    es_externo = models.BooleanField(default=False, verbose_name="¿Es colaborador externo?")
    institucion_origen = models.CharField(
        max_length=200,
        default="UABC",
        verbose_name="Institución o Universidad de procedencia"
    )

    fecha_nacimiento = models.DateField(blank=True, null=True, verbose_name="Fecha de Nacimiento")
    genero = models.CharField(max_length=5, choices=GENERO_OPCIONES, default='NE', verbose_name="Género")
    genero_otro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Especificar género")

    # --- DATOS OFICIALES PÚBLICOS (Los que lee el claustro) ---
    foto_perfil = models.ImageField(upload_to='profesores/', blank=True, null=True,
                                    verbose_name="Foto Oficial (Claustro Docente)")
    biografia = models.TextField(blank=True, null=True, verbose_name="Semblanza Académica / Biografía (Resumen)")
    biografia_extendida = models.TextField(blank=True, null=True, verbose_name="Biografía Detallada Completa")
    reconocimiento_pdf = models.FileField(upload_to='reconocimientos/', blank=True, null=True,
                                          verbose_name="PDF de Reconocimientos / CV")

    # --- DATOS EN BORRADOR / EDICIÓN PRIVADA DEL PROFESOR ---
    foto_perfil_borrador = models.ImageField(upload_to='profesores/borradores/', blank=True, null=True,
                                             verbose_name="Foto Oficial en Borrador")
    biografia_borrador = models.TextField(blank=True, null=True, verbose_name="Biografía en Borrador")
    biografia_extendida_borrador = models.TextField(blank=True, null=True, verbose_name="Biografía Detallada en Borrador")
    reconocimiento_pdf_borrador = models.FileField(upload_to='reconocimientos/borradores/', blank=True, null=True,
                                                   verbose_name="PDF de Reconocimientos en Borrador")

    # --- FOTO PERSONAL (Exclusiva del panel del usuario) ---
    foto_personal = models.ImageField(upload_to='perfiles/', blank=True, null=True,
                                      verbose_name="Foto de Perfil Personal (Panel)")

    rol_facultad = models.CharField(max_length=10, choices=ROL_DOCENTE_OPCIONES, default='OTRO',
                                    verbose_name="Cargo o Nivel Principal en Facultad")

    perfil_completado = models.BooleanField(default=False, verbose_name="¿Ficha pública completada en claustro?")

    ESTADOS_SEMBLANZA = [
        ('borrador', 'Borrador / Sin Enviar'),
        ('pendiente', 'Pendiente de Revisión'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    estado_semblanza = models.CharField(max_length=20, choices=ESTADOS_SEMBLANZA, default='borrador',
                                        verbose_name="Estado de Semblanza")
    motivo_rechazo_semblanza = models.TextField(blank=True, null=True, verbose_name="Motivo de rechazo de semblanza")
    moderado_por_semblanza = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='semblanzas_moderadas',
        verbose_name="Semblanza moderada por"
    )

    @property
    def es_cumpleanos_hoy(self):
        """Determina si el día y mes actual coinciden con la fecha de nacimiento del docente."""
        if not self.fecha_nacimiento:
            return False
        hoy = timezone.localdate()
        return self.fecha_nacimiento.day == hoy.day and self.fecha_nacimiento.month == hoy.month

    def __str__(self):
        if self.es_externo:
            return f"{self.nombre} ({self.institucion_origen})"
        if self.es_profesor:
            return f"{self.nombre} (Profesor UABC)"
        return f"{self.nombre} (UABC)"


class EnlaceProfesional(models.Model):
    """Modelo para las burbujas/tags de enlaces profesionales y redes de los autores."""
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, related_name='enlaces_profesionales')
    plataforma = models.CharField(max_length=50, verbose_name="Plataforma o Red (ej. GitHub, SSRN, LinkedIn)")
    url = models.URLField(max_length=300, verbose_name="Enlace URL")
    emoji = models.CharField(max_length=10, default="🔗", verbose_name="Emoji o Ícono")

    def __str__(self):
        return f"{self.emoji} {self.plataforma} - {self.autor.nombre}"


class MensajeCumpleanos(models.Model):
    """Mensajes institucionales de felicitación enviados por colegas docentes."""
    para_docente = models.ForeignKey(Autor, on_delete=models.CASCADE, related_name='mensajes_recibidos')
    de_usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mensajes_enviados')
    mensaje = models.CharField(max_length=300)
    fecha_envio = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_envio']

    def __str__(self):
        return f"Felicitación de {self.de_usuario.username} para {self.para_docente.nombre}"


class Entidad(models.Model):
    nombre = models.CharField(max_length=150)

    def __str__(self):
        return self.nombre


class TipoContenido(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Area(models.Model):
    nombre = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre


class Articulo(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente de Revisión'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]

    autor = models.ManyToManyField(Autor, related_name='documentos')
    entidad = models.ForeignKey(Entidad, on_delete=models.CASCADE)
    tipo_contenido = models.ForeignKey(TipoContenido, on_delete=models.CASCADE)
    area = models.ForeignKey(Area, on_delete=models.CASCADE)
    subido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='articulos_subidos')

    titulo = models.CharField(max_length=255)
    descripcion = models.TextField(verbose_name="Resumen / Descripción")
    año_produccion = models.IntegerField(verbose_name="Año de producción")
    palabras_clave = models.CharField(max_length=255, blank=True, null=True, help_text="Separadas por comas")
    idioma = models.CharField(max_length=50, default="Español")

    asesor = models.ForeignKey(
        Autor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tesis_asesoradas',
        verbose_name="Director / Asesor de Tesis"
    )
    grado_academico = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        choices=[
            ('Licenciatura', 'Licenciatura'),
            ('Especialidad', 'Especialidad'),
            ('Maestria', 'Maestría'),
            ('Doctorado', 'Doctorado'),
        ]
    )
    carrera_o_posgrado = models.CharField(max_length=150, blank=True, null=True,
                                          verbose_name="Programa Académico / Carrera")

    editorial = models.CharField(max_length=150, blank=True, null=True)
    revista = models.CharField(max_length=150, blank=True, null=True)
    isbn_issn = models.CharField(max_length=50, blank=True, null=True, verbose_name="ISBN / ISSN")
    volumen_numero = models.CharField(max_length=50, blank=True, null=True, verbose_name="Volumen / Número")
    paginas = models.CharField(max_length=50, blank=True, null=True, verbose_name="Páginas (ej. 15-30)")
    doi_enlace = models.CharField(max_length=255, blank=True, null=True, verbose_name="DOI o Enlace persistente")

    pdf = models.FileField(upload_to='pdfs/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    motivo_rechazo = models.TextField(blank=True, null=True, verbose_name="Motivo del rechazo (si aplica)")

    moderado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articulos_moderados',
        verbose_name="Moderado/Rechazado por"
    )

    @property
    def esta_publicado(self):
        return self.estado == 'aprobado'

    def __str__(self):
        return f"{self.titulo} ({self.año_produccion}) - [{self.estado}]"