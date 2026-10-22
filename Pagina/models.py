from django.db import models
from django.db.models import Q
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
    ('DIR', 'Directora / Director de Facultad'),
    ('SUBDIR', 'Subdirectora / Subdirector'),
    ('COORD', 'Coordinador Académico'),
    ('COORD_POS', 'Coordinador de Posgrado'),
    ('COORD_LIC', 'Coordinador de Carrera / Licenciatura'),
    ('PTC', 'Profesor de Tiempo Completo (PTC)'),
    ('ASIG', 'Profesor de Asignatura'),
    ('INV', 'Investigador / SNII'),
    ('CA', 'Miembro de Cuerpo Académico'),
    ('ACAD', 'Presidente / Secretario de Academia'),
    ('TUTOR', 'Tutor Académico / Asesor de Tesis'),
    ('SINODAL', 'Sinodal / Comité de Titulación'),
    ('VINC', 'Coordinador de Vinculación y Prácticas'),
    ('RESP_LAB', 'Responsable de Laboratorio / Cómputo'),
    ('INV_IND', 'Investigador / Consultor sin Adscripción Fija'),
    ('EXT', 'Colaborador Externo'),
    ('AUX_INV', 'Auxiliar de Investigación FCA'),
    ('DEP_TEC', 'Operador Técnico / Depurador de Contenidos'),
    ('SOPORTE', 'Soporte Técnico / Administración'),
    ('EMER', 'Profesor Emérito'),
    ('OTRO', 'Docente / Investigador'),
    ('CUSTOM', 'Cargo Específico Personalizado'),
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
    rol = models.CharField(max_length=20, choices=ROL_DOCENTE_OPCIONES, verbose_name="Cargo o Nivel")
    cargo_personalizado = models.CharField(max_length=150, blank=True, null=True, verbose_name="Cargo Personalizado")

    def get_rol_display_text(self):
        if self.rol == 'CUSTOM' and self.cargo_personalizado:
            return self.cargo_personalizado
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
    # --- IDENTIFICACIÓN NORMALIZADA Y CÓDIGO INSTITUCIONAL ---
    titulo_academico = models.CharField(max_length=30, blank=True, null=True, verbose_name="Título o Grado Académico (Prefijo: Dr., Dra., Mtro., Lic., etc.)")
    nombres = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nombre(s)")
    apellido_paterno = models.CharField(max_length=80, blank=True, null=True, verbose_name="Apellido Paterno")
    apellido_materno = models.CharField(max_length=80, blank=True, null=True, verbose_name="Apellido Materno")
    codigo_institucional = models.CharField(max_length=30, unique=True, blank=True, null=True,
                                            verbose_name="Código de Autor Institucional (FCA-ID)")
    orcid = models.CharField(max_length=30, blank=True, null=True, verbose_name="Identificador ORCID (Opcional)")

    numero_empleado = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True, verbose_name="Fecha de Registro")
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
    horario_pdf = models.FileField(upload_to='horarios/', blank=True, null=True,
                                   verbose_name="Horario de Clases y Asesorías (PDF)")

    # --- DATOS EN BORRADOR / EDICIÓN PRIVADA DEL PROFESOR ---
    foto_perfil_borrador = models.ImageField(upload_to='profesores/borradores/', blank=True, null=True,
                                             verbose_name="Foto Oficial en Borrador")
    biografia_borrador = models.TextField(blank=True, null=True, verbose_name="Biografía en Borrador")
    biografia_extendida_borrador = models.TextField(blank=True, null=True, verbose_name="Biografía Detallada en Borrador")
    reconocimiento_pdf_borrador = models.FileField(upload_to='reconocimientos/borradores/', blank=True, null=True,
                                                   verbose_name="PDF de Reconocimientos en Borrador")
    horario_pdf_borrador = models.FileField(upload_to='horarios/borradores/', blank=True, null=True,
                                            verbose_name="Horario en Borrador (PDF)")

    # --- FOTO PERSONAL (Exclusiva del panel del usuario) ---
    foto_personal = models.ImageField(upload_to='perfiles/', blank=True, null=True,
                                      verbose_name="Foto de Perfil Personal (Panel)")

    COLORES_CUMPLEANOS = [
        ('rosa', 'Fresa Glaseada (Rosa)'),
        ('cafe', 'Chocolate & Moka (Café)'),
        ('azul', 'Arándano Silvestre (Azul)'),
        ('verde', 'Menta & Pistache (Verde)'),
        ('dorado', 'Vainilla & Caramelo (Dorado)'),
        ('morado', 'Mora & Lavanda (Morado)'),
        ('rojo', 'Red Velvet (Rojo Cereza)'),
    ]
    color_cumpleanos = models.CharField(
        max_length=20,
        choices=COLORES_CUMPLEANOS,
        default='rosa',
        verbose_name="Color/Sabor del Cupcake de Cumpleaños"
    )

    rol_facultad = models.CharField(max_length=20, choices=ROL_DOCENTE_OPCIONES, default='OTRO',
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

    # --- GESTIÓN DE ACCESO, PERMISOS Y SUSPENSIÓN ---
    is_trusted_publisher = models.BooleanField(
        default=False,
        verbose_name="Publicador de Confianza (Bypass de Moderación)"
    )

    ESTADOS_CUENTA = [
        ('activa', 'Cuenta Activa'),
        ('pendiente', 'Solicitud Pendiente de Aprobación'),
        ('pendiente_verificacion', 'Pendiente de Verificación de Correo'),
        ('suspendida', 'Cuenta Suspendida'),
        ('baja_voluntaria', 'Baja por el Usuario'),
    ]
    estado_cuenta = models.CharField(
        max_length=30,
        choices=ESTADOS_CUENTA,
        default='activa',
        verbose_name="Estado de la Cuenta"
    )

    # --- AUTENTICACIÓN Y SEGURIDAD: CÓDIGOS OTP (EXPIRACIÓN 15 MINUTOS) ---
    correo_verificado = models.BooleanField(
        default=False,
        verbose_name="¿Correo electrónico autenticado/verificado?"
    )
    codigo_verificacion = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name="Código de Verificación OTP"
    )
    codigo_verificacion_expira = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha y Hora de Expiración del Código"
    )
    codigo_recuperacion = models.CharField(
        max_length=6,
        blank=True,
        null=True,
        verbose_name="Código de Recuperación de Contraseña"
    )
    codigo_recuperacion_expira = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de Expiración de Recuperación"
    )
    motivo_suspension = models.TextField(
        blank=True,
        null=True,
        verbose_name="Motivo de Suspensión o Baja"
    )
    fecha_suspension = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha y Hora de Suspensión"
    )
    fecha_fin_suspension = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fin de Suspensión (Expiración)"
    )
    suspendido_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuentas_suspendidas_admin',
        verbose_name="Suspendido por"
    )

    # --- SOLICITUD DE REACTIVACIÓN DE CUENTA ---
    solicitud_reactivacion = models.BooleanField(
        default=False,
        verbose_name="¿Ha solicitado reactivación de cuenta?"
    )
    motivo_reactivacion = models.TextField(
        blank=True,
        null=True,
        verbose_name="Mensaje o Motivo de Solicitud de Reactivación"
    )
    fecha_solicitud_reactivacion = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de Solicitud de Reactivación"
    )
    contacto_reactivacion = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        verbose_name="Correo o Teléfono de Contacto Alternativo"
    )

    # --- ROL Y VINCULACIÓN: AUXILIAR DE INVESTIGACIÓN FCA ---
    es_auxiliar = models.BooleanField(
        default=False,
        verbose_name="¿Es Auxiliar de Investigación FCA?"
    )
    profesor_tutor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auxiliares_asignados',
        verbose_name="Profesor Tutor / Responsable Académico UABC"
    )
    matricula_estudiante = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Matrícula Estudiantil o Folio de Servicio Social"
    )
    modalidad_auxiliar = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name="Modalidad (SSP, Prácticas, Asistente de Investigación, Tesista)"
    )
    aprobado_por_tutor = models.BooleanField(
        default=False,
        verbose_name="¿Visto Bueno otorgado por el Profesor Tutor?"
    )
    fecha_aprobacion_tutor = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha y Hora de Aprobación del Tutor"
    )

    # --- ROL: OPERADOR TÉCNICO / DEPURADOR DE CONTENIDOS (CENTRO DE COPIADO / CÓMPUTO) ---
    es_operador_tecnico = models.BooleanField(
        default=False,
        verbose_name="¿Es Operador Técnico / Depurador de Contenidos?"
    )

    # --- ROL: SOPORTE TÉCNICO / ADMINISTRACIÓN (VÍA DE REGISTRO SUPERADMIN) ---
    es_soporte = models.BooleanField(
        default=False,
        verbose_name="¿Es Personal de Soporte Técnico / Administración?"
    )

    @property
    def esta_suspendido_vigente(self):
        """Verifica si la cuenta está suspendida y si la suspensión sigue vigente."""
        if self.estado_cuenta != 'suspendida':
            return False
        if self.fecha_fin_suspension:
            return timezone.now() < self.fecha_fin_suspension
        return True

    @property
    def es_cumpleanos_hoy(self):
        """Determina si el día y mes actual coinciden con la fecha de nacimiento del docente."""
        if not self.fecha_nacimiento:
            return False
        hoy = timezone.localdate()
        return self.fecha_nacimiento.day == hoy.day and self.fecha_nacimiento.month == hoy.month

    @property
    def nombre_con_titulo(self):
        """
        Devuelve el nombre con el grado o título académico para presentación en el Claustro Docente.
        Ej: 'Dr. Pugberto Almaeda Canino López'
        """
        if self.titulo_academico:
            tit = self.titulo_academico.strip()
            nom = (self.nombre or '').strip()
            if tit and not nom.lower().startswith(tit.lower()):
                return f"{tit} {nom}".strip()
        return (self.nombre or '').strip()

    @property
    def foto_claustro_url(self):
        """
        Retorna la URL de la fotografía oficial aceptada del claustro docente si existe.
        """
        if self.foto_perfil and hasattr(self.foto_perfil, 'url'):
            try:
                return self.foto_perfil.url
            except Exception:
                pass
        if self.foto_personal and hasattr(self.foto_personal, 'url'):
            try:
                return self.foto_personal.url
            except Exception:
                pass
        return None

    @property
    def total_obras_aprobadas(self):
        """Retorna el número de publicaciones académicas aprobadas y activas (no en papelera)."""
        return self.documentos.filter(estado='aprobado', en_papelera=False).count()

    @property
    def total_asesorias(self):
        """Retorna el total de tesis o proyectos donde fue asesor o coasesor de obras aprobadas."""
        return Articulo.objects.filter(
            Q(asesor=self) | Q(coasesor=self),
            estado='aprobado',
            en_papelera=False
        ).distinct().count()

    @property
    def medalla_productividad(self):
        """
        Calcula el nivel de reconocimiento académico por producción aprobada:
        - Oro (10+ obras)
        - Plata (5 - 9 obras)
        - Bronce (1 - 4 obras)
        - Sin medalla (0 obras)
        """
        obras = self.total_obras_aprobadas
        if obras >= 10:
            return {
                'nivel': 'oro',
                'titulo': 'Investigador Nivel Oro',
                'badge_class': 'bg-warning text-dark border border-warning shadow-xs',
                'icono': 'fas fa-medal text-warning',
                'emoji': '🥇',
                'descripcion': 'Más de 10 publicaciones científicas arbitradas'
            }
        elif obras >= 5:
            return {
                'nivel': 'plata',
                'titulo': 'Investigador Nivel Plata',
                'badge_class': 'bg-light text-secondary border shadow-xs',
                'icono': 'fas fa-medal text-secondary',
                'emoji': '🥈',
                'descripcion': 'Entre 5 y 9 publicaciones científicas'
            }
        elif obras >= 1:
            return {
                'nivel': 'bronce',
                'titulo': 'Investigador Nivel Bronce',
                'badge_class': 'bg-light text-dark border shadow-xs',
                'icono': 'fas fa-award text-secondary',
                'emoji': '🥉',
                'descripcion': 'Publicaciones activas en el repositorio'
            }
        return None

    @property
    def inicial_limpia(self):
        """
        Devuelve la inicial del nombre real del docente (ignora títulos y prefijos académicos como Dr., Dra., Mtro., Lic., etc.).
        """
        import re
        nom = (self.nombre or '').strip()
        limpio = re.sub(r'^(dr\.|dra\.|mtro\.|mtra\.|lic\.|ing\.|prof\.|profa\.|phd\.|m\.c\.)\s*', '', nom, flags=re.IGNORECASE).strip()
        if limpio:
            return limpio[:1].upper()
        if self.nombres:
            n_limpio = re.sub(r'^(dr\.|dra\.|mtro\.|mtra\.|lic\.|ing\.|prof\.|profa\.|phd\.|m\.c\.)\s*', '', self.nombres.strip(), flags=re.IGNORECASE).strip()
            if n_limpio:
                return n_limpio[:1].upper()
        if self.apellido_paterno:
            return self.apellido_paterno.strip()[:1].upper()
        return nom[:1].upper() if nom else '?'

    def obtener_prefijo_codigo_institucional(self):
        """
        Determina el prefijo del código institucional:
        - 'INV': Para investigadores independientes / externos (INV_IND o 'independiente').
        - 'FCA': Para docentes y personal de UABC / FCA.
        - Siglas de la universidad (ej. 'UNAM', 'IPN', 'ITCG'): Para docentes de otras universidades.
        """
        import re
        if self.rol_facultad == 'INV_IND' or 'independiente' in (self.institucion_origen or '').lower():
            return 'INV'
        inst = (self.institucion_origen or '').strip()
        if not inst or inst.upper() == 'UABC' or not self.es_externo:
            return 'FCA'
        # Buscar acrónimo entre paréntesis, ej: 'Universidad Nacional Autónoma de México (UNAM)' -> 'UNAM'
        match = re.search(r'\(([A-Za-z0-9\-_]+)\)', inst)
        if match:
            return match.group(1).upper()
        # Buscar en catálogo de universidades
        uni = Universidad.objects.filter(nombre__iexact=inst).first()
        if uni and uni.siglas:
            return uni.siglas.upper()
        # Fallback limpio alfanumérico
        clean = re.sub(r'[^A-Za-z0-9]', '', inst)
        return clean[:6].upper() if clean else 'EXT'

    def save(self, *args, **kwargs):
        # Sincronización automática de nombre si están los componentes y no se fijó un nombre explícito
        if self.nombres and self.apellido_paterno:
            partes = [self.nombres.strip(), self.apellido_paterno.strip()]
            if self.apellido_materno:
                partes.append(self.apellido_materno.strip())
            if not self.nombre:
                self.nombre = " ".join(partes)

        # Generación garantizada de código institucional único (FCA-ID, UNAM-ID, INV-ID, etc.)
        prefijo = self.obtener_prefijo_codigo_institucional()
        if not self.codigo_institucional:
            ultimo = Autor.objects.order_by('-id').first()
            siguiente_num = (ultimo.id + 1001) if (ultimo and ultimo.id) else 1001
            candidato = f"{prefijo}-{siguiente_num}"
            offset = 1
            while Autor.objects.filter(codigo_institucional=candidato).exclude(pk=self.pk).exists():
                candidato = f"{prefijo}-{siguiente_num + offset}"
                offset += 1
            self.codigo_institucional = candidato

        super().save(*args, **kwargs)

    def __str__(self):
        prefijo = f"[{self.codigo_institucional}] " if self.codigo_institucional else ""
        if self.es_externo:
            return f"{prefijo}{self.nombre} ({self.institucion_origen})"
        if self.es_profesor:
            return f"{prefijo}{self.nombre} (Profesor UABC)"
        return f"{prefijo}{self.nombre} (UABC)"


class EnlaceProfesional(models.Model):
    """Modelo para las burbujas/tags de enlaces profesionales y redes de los autores."""
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, related_name='enlaces_profesionales')
    plataforma = models.CharField(max_length=50, verbose_name="Plataforma o Red (ej. GitHub, SSRN, LinkedIn)")
    url = models.URLField(max_length=300, verbose_name="Enlace URL")
    emoji = models.CharField(max_length=20, default="🔗", verbose_name="Emoji o Ícono")

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
    coasesor = models.ForeignKey(
        Autor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tesis_coasesoradas',
        verbose_name="Co-director / Co-asesor de Tesis"
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

    es_subida_automatica = models.BooleanField(
        default=False,
        verbose_name="Subida Automática por Usuario de Confianza"
    )

    chequeado_por_moderador = models.BooleanField(
        default=False,
        verbose_name="Archivo Cotejado / Checado por Moderador"
    )

    chequeado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articulos_chequeados',
        verbose_name="Checado/Cotejado por"
    )

    fecha_chequeado = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha en que fue checado"
    )

    # SOPORTE DE PAPELERA DE RECICLAJE (SOFT-DELETE)
    en_papelera = models.BooleanField(
        default=False,
        verbose_name="En Papelera de Reciclaje"
    )
    fecha_eliminacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de envío a papelera"
    )
    eliminado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articulos_eliminados',
        verbose_name="Enviado a papelera por"
    )

    @property
    def esta_publicado(self):
        return self.estado == 'aprobado' and not self.en_papelera

    def __str__(self):
        return f"{self.titulo} ({self.año_produccion}) - [{self.estado}]"


# ==============================================================================
# MÓDULO 5: COLABORACIÓN, COAUTORÍAS Y MENSAJERÍA INTERNA
# ==============================================================================

class InvitacionCoautoria(models.Model):
    """Gestión de solicitudes de confirmación de coautoría entre académicos."""
    ESTADOS = [
        ('pendiente', 'Pendiente de Confirmación'),
        ('aceptada', 'Aceptada'),
        ('rechazada', 'Rechazada'),
    ]
    articulo = models.ForeignKey(Articulo, on_delete=models.CASCADE, related_name='invitaciones_coautoria')
    autor_invitado = models.ForeignKey(Autor, on_delete=models.CASCADE, related_name='invitaciones_recibidas')
    invitado_por = models.ForeignKey(User, on_delete=models.CASCADE, related_name='invitaciones_enviadas')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    mensaje = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nota / Mensaje de invitación")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-fecha_creacion']
        unique_together = ('articulo', 'autor_invitado')
        verbose_name = "Invitación de Coautoría"
        verbose_name_plural = "Invitaciones de Coautoría"

    def __str__(self):
        return f"Invitación a {self.autor_invitado.nombre} para '{self.articulo.titulo}' [{self.estado}]"


class MensajeInterno(models.Model):
    """Sistema de mensajería académica interna directa entre docentes del repositorio y soporte."""
    remitente = models.ForeignKey(User, on_delete=models.CASCADE, related_name='mensajes_academicos_enviados')
    destinatario = models.ForeignKey(Autor, on_delete=models.CASCADE, null=True, blank=True, related_name='mensajes_academicos_recibidos')
    es_soporte = models.BooleanField(default=False, verbose_name="¿Es consulta a Soporte?")
    atendido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='mensajes_soporte_atendidos', verbose_name="Admin que atendió")
    estado_soporte = models.CharField(max_length=20, default='abierto', choices=[('abierto', 'Abierto'), ('en_proceso', 'En Atención'), ('resuelto', 'Resuelto')])
    asunto = models.CharField(max_length=150, verbose_name="Asunto")
    cuerpo = models.TextField(verbose_name="Mensaje")
    adjunto = models.FileField(upload_to='mensajes_adjuntos/', blank=True, null=True, verbose_name="Archivo Adjunto")
    nombre_adjunto = models.CharField(max_length=255, blank=True, null=True, verbose_name="Nombre original del archivo")
    leido = models.BooleanField(default=False, verbose_name="¿Leído?")
    fecha_envio = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Envío")

    class Meta:
        ordering = ['-fecha_envio']
        verbose_name = "Mensaje Académico Interno"
        verbose_name_plural = "Mensajes Académicos Internos"

    def __str__(self):
        destino = "Soporte Institucional" if self.es_soporte else (self.destinatario.nombre if self.destinatario else "S/D")
        return f"De {self.remitente.username} para {destino}: {self.asunto}"

    @property
    def extension_adjunto(self):
        if self.adjunto:
            import os
            _, ext = os.path.splitext(self.adjunto.name)
            return ext.lower().replace('.', '')
        return ''

    @property
    def es_imagen(self):
        return self.extension_adjunto in ['jpg', 'jpeg', 'png', 'gif', 'webp']

    @property
    def es_pdf(self):
        return self.extension_adjunto == 'pdf'

    @property
    def es_documento(self):
        return self.extension_adjunto in ['doc', 'docx', 'odt', 'rtf']

    @property
    def es_presentacion(self):
        return self.extension_adjunto in ['ppt', 'pptx', 'odp']

    @property
    def es_hoja_calculo(self):
        return self.extension_adjunto in ['xls', 'xlsx', 'csv', 'ods']


class HistorialFusion(models.Model):
    """
    Registra cada operación de fusión de autores para auditoría detallada
    y permite revertir (deshacer) la fusión restaurando los perfiles absorbidos y sus obras.
    """
    admin_usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Admin que ejecutó la fusión")
    autor_principal = models.ForeignKey('Autor', on_delete=models.CASCADE, related_name='fusiones_recibidas', verbose_name="Autor Canónico Principal")
    nombre_principal_snapshot = models.CharField(max_length=200, verbose_name="Nombre Principal al Fusionar")
    codigo_principal_snapshot = models.CharField(max_length=50, blank=True, null=True, verbose_name="Código FCA-ID Principal")

    # JSON con el snapshot completo de los duplicados y los IDs de obras/tesis transferidas
    datos_duplicados_json = models.TextField(verbose_name="Datos serializados de duplicados y recursos transferidos")

    total_obras_transferidas = models.IntegerField(default=0, verbose_name="Obras Transferidas")
    total_asesorias_transferidas = models.IntegerField(default=0, verbose_name="Asesorías Transferidas")

    revertida = models.BooleanField(default=False, verbose_name="¿Fusión Revertida?")
    fecha_fusion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Fusión")
    fecha_reversion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Reversión")
    revertida_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='fusiones_revertidas', verbose_name="Admin que revirtió")

    class Meta:
        ordering = ['-fecha_fusion']
        verbose_name = "Historial de Fusión de Autores"
        verbose_name_plural = "Historiales de Fusiones de Autores"

    def __str__(self):
        estado = " [REVERTIDA]" if self.revertida else ""
        return f"Fusión en {self.nombre_principal_snapshot} ({self.fecha_fusion.strftime('%d/%m/%Y %H:%M')}){estado}"

    def get_duplicados_list(self):
        import json
        try:
            return json.loads(self.datos_duplicados_json)
        except Exception:
            return []
