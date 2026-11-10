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
                                    verbose_name="Foto Oficial (Claustro Docente e Investigadores)")
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

    # --- LÍNEAS DE INVESTIGACIÓN Y ESPECIALIDAD (IDEA 24) ---
    lineas_investigacion = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name="Líneas de Investigación y Especialidad (separadas por coma)"
    )
    lineas_investigacion_borrador = models.CharField(
        max_length=500, blank=True, null=True,
        verbose_name="Líneas de Investigación en Borrador"
    )

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
    aprobado_por_soporte_1 = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuentas_soporte_avaladas_1',
        verbose_name="Primera firma de aprobación de soporte"
    )
    fecha_aprobacion_soporte_1 = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de primera aprobación de soporte"
    )
    aprobado_por_soporte_2 = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cuentas_soporte_avaladas_2',
        verbose_name="Segunda firma de aprobación de soporte"
    )
    fecha_aprobacion_soporte_2 = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Fecha de segunda aprobación de soporte"
    )

    @property
    def puede_tener_semblanza(self):
        """
        Determina si el usuario o autor tiene derecho a contar con ficha académica y semblanza pública.
        Las semblanzas están reservadas exclusivamente para:
        1. Docentes UABC (FCA)
        2. Docentes / Colaboradores de otras universidades
        3. Investigadores (adscritos o independientes)

        NO aplica para:
        - Super Administradores de la plataforma (is_superuser=True)
        - Auxiliares de investigación FCA
        - Personal de Soporte Técnico ni Operadores Técnicos
        """
        if self.usuario and self.usuario.is_superuser:
            return False
        if self.es_auxiliar or self.rol_facultad in ['AUX_INV', 'SOPORTE', 'DEP_TEC'] or getattr(self, 'es_soporte', False) or getattr(self, 'es_operador_tecnico', False):
            return False
        if self.es_externo or self.rol_facultad == 'EXT':
            return True
        if self.rol_facultad in ['INV', 'INV_IND'] or 'independiente' in (self.institucion_origen or '').lower():
            return True
        roles_academicos = [
            'PTC', 'ASIG', 'COORD_LIC', 'CA', 'ACAD', 'TUTOR',
            'SINODAL', 'VINC', 'RESP_LAB', 'EMER', 'OTRO', 'CUSTOM'
        ]
        return bool(self.es_profesor or self.rol_facultad in roles_academicos)

    @property
    def puede_tener_auxiliares(self):
        """
        Solo los docentes adscritos a la UABC pueden tener auxiliares de investigación vinculados.
        """
        if not self.puede_tener_semblanza:
            return False
        if self.es_externo or self.rol_facultad in ['EXT', 'INV_IND']:
            return False
        if 'independiente' in (self.institucion_origen or '').lower():
            return False
        return True

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
        Devuelve el nombre con el grado o título académico para presentación en el Claustro Docente e Investigadores.
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
        Retorna la URL de la fotografía oficial aceptada del claustro docente e investigadores si existe.
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
    def progreso_productividad(self):
        """
        Calcula el progreso hacia el siguiente nivel de medalla académica (Idea 25).
        """
        obras = self.total_obras_aprobadas
        if obras >= 10:
            return {
                'actual': self.medalla_productividad,
                'siguiente_titulo': None,
                'siguiente_emoji': '👑',
                'porcentaje': 100,
                'faltantes': 0,
                'es_maximo': True,
                'meta': 10,
                'obras': obras
            }
        elif obras >= 5:
            return {
                'actual': self.medalla_productividad,
                'siguiente_titulo': 'Investigador Nivel Oro',
                'siguiente_emoji': '🥇',
                'porcentaje': int((obras / 10) * 100),
                'faltantes': 10 - obras,
                'es_maximo': False,
                'meta': 10,
                'obras': obras
            }
        elif obras >= 1:
            return {
                'actual': self.medalla_productividad,
                'siguiente_titulo': 'Investigador Nivel Plata',
                'siguiente_emoji': '🥈',
                'porcentaje': int((obras / 5) * 100),
                'faltantes': 5 - obras,
                'es_maximo': False,
                'meta': 5,
                'obras': obras
            }
        else:
            return {
                'actual': {
                    'nivel': 'iniciador',
                    'titulo': 'Investigador Iniciador',
                    'badge_class': 'bg-light text-muted border shadow-xs',
                    'icono': 'fas fa-seedling text-muted',
                    'emoji': '🌱',
                    'descripcion': 'Iniciando trayectoria en el repositorio'
                },
                'siguiente_titulo': 'Investigador Nivel Bronce',
                'siguiente_emoji': '🥉',
                'porcentaje': 0,
                'faltantes': 1,
                'es_maximo': False,
                'meta': 1,
                'obras': 0
            }

    @property
    def lista_lineas_investigacion(self):
        """Lista de líneas de investigación activas (borrador o públicas) para edición interactiva."""
        txt = self.lineas_investigacion_borrador if self.lineas_investigacion_borrador is not None else self.lineas_investigacion
        if not txt:
            return []
        return [l.strip() for l in txt.split(',') if l.strip()]

    @property
    def lista_lineas_investigacion_publicas(self):
        """Lista de líneas de investigación públicas aprobadas para vista en claustro."""
        if not self.lineas_investigacion:
            return []
        return [l.strip() for l in self.lineas_investigacion.split(',') if l.strip()]

    @property
    def siglas_institucion(self):
        """Devuelve las siglas o acrónimo limpio de la institución de procedencia (Idea 16)."""
        return self.obtener_prefijo_codigo_institucional()

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
        if self.rol_facultad == 'INV_IND' or 'independiente' in (self.institucion_origen or '').lower() or (self.institucion_origen or '').lower().startswith('investigador'):
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
        elif '-' in self.codigo_institucional:
            # Sincronizar prefijo si el rol o procedencia institucional cambió (ej. FCA-1212 -> INV-1212)
            prefijo_actual, num_actual = self.codigo_institucional.split('-', 1)
            if prefijo == 'INV' and prefijo_actual != 'INV':
                candidato = f"INV-{num_actual}"
                if not Autor.objects.filter(codigo_institucional=candidato).exclude(pk=self.pk).exists():
                    self.codigo_institucional = candidato
            elif prefijo == 'FCA' and prefijo_actual != 'FCA' and not self.es_externo and self.rol_facultad != 'INV_IND':
                candidato = f"FCA-{num_actual}"
                if not Autor.objects.filter(codigo_institucional=candidato).exclude(pk=self.pk).exists():
                    self.codigo_institucional = candidato

        # Superadministradores nunca deben marcarse como docentes académicos
        if self.usuario and self.usuario.is_superuser:
            self.es_profesor = False
            self.perfil_completado = False
            if self.rol_facultad in ['OTRO', 'PTC', 'ASIG']:
                self.rol_facultad = 'SOPORTE'

        super().save(*args, **kwargs)

    def __str__(self):
        prefijo = f"[{self.codigo_institucional}] " if self.codigo_institucional else ""
        if self.usuario and self.usuario.is_superuser:
            return f"{prefijo}{self.nombre} (Super Administrador)"
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

    # -------------------------------------------------------------
    # CAMPOS RIZOMA / CONAHCYT - PRODUCCIÓN TECNOLÓGICA & ESPECIALIZADA
    # -------------------------------------------------------------
    # A. Propiedad Intelectual (INDAUTOR / IMPI)
    tipo_proteccion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo de Protección (INDAUTOR/IMPI)")
    numero_registro = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Registro o Solicitud")
    rama_propiedad = models.CharField(max_length=120, blank=True, null=True, verbose_name="Rama / Categoría de la Obra")
    titular_propiedad = models.CharField(max_length=255, blank=True, null=True, default="Universidad Autónoma de Baja California", verbose_name="Titular de los Derechos")
    rol_participacion = models.CharField(max_length=100, blank=True, null=True, verbose_name="Rol de Participación")
    ambito_solicitud = models.CharField(max_length=50, blank=True, null=True, default="México", verbose_name="Ámbito de Solicitud (México/Internacional/Ambas)")
    fecha_expedicion_solicitud = models.DateField(blank=True, null=True, verbose_name="Fecha de Expedición o Presentación")
    estado_propiedad = models.CharField(max_length=80, blank=True, null=True, verbose_name="Estado de la Solicitud / Registro")
    solicitud_internacional_numero = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Solicitud Internacional (PCT)")
    publicacion_internacional_numero = models.CharField(max_length=100, blank=True, null=True, verbose_name="Número de Publicación Internacional")

    # B. Desarrollo Tecnológico e Innovación
    tipo_desarrollo = models.CharField(max_length=100, blank=True, null=True, verbose_name="Tipo de Desarrollo")
    problema_atiende = models.TextField(blank=True, null=True, verbose_name="Problema o Necesidad que Atiende")
    beneficiarios_impacto = models.TextField(blank=True, null=True, verbose_name="Población o Sector Beneficiado / Impacto")

    # C. Transferencia Tecnológica
    institucion_receptora = models.CharField(max_length=255, blank=True, null=True, verbose_name="Institución o Empresa Receptora")
    tipo_transferencia = models.CharField(max_length=120, blank=True, null=True, verbose_name="Modalidad de Transferencia")

    # D. Traducciones Científicas
    idioma_original = models.CharField(max_length=80, blank=True, null=True, verbose_name="Idioma de la Obra Original")
    titulo_original = models.CharField(max_length=255, blank=True, null=True, verbose_name="Título de la Obra Original")
    autor_original = models.CharField(max_length=255, blank=True, null=True, verbose_name="Autor(es) de la Obra Original")

    # E. Antología / Dossier / Prólogo / Informes
    nombre_compilador_coordinador = models.CharField(max_length=255, blank=True, null=True, verbose_name="Compilador / Coordinador de la Obra")
    obra_receptora = models.CharField(max_length=255, blank=True, null=True, verbose_name="Libro o Publicación Donde se Incluye")
    proyecto_origen = models.CharField(max_length=255, blank=True, null=True, verbose_name="Proyecto o Institución Financiadora")

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

    @property
    def folio_institucional(self):
        year = self.created_at.year if self.created_at else (self.año_produccion or 2026)
        return f"FOLIO-FCA-{year}-{self.id:05d}"

    @property
    def hash_sello_digital(self):
        import hashlib
        raw = f"{self.id}-{self.titulo}-{self.created_at}-{self.subido_por_id}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32].upper()

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


class ConfiguracionSistema(models.Model):
    """
    Configuración central y dinámica del sistema (Singleton).
    Permite modificar las credenciales de correo automático y los datos
    de soporte para docentes sin tocar el código fuente.
    """
    # 1. Configuración de Correo Automático (Gmail / SMTP)
    email_host_user = models.EmailField(
        default='pruebarepsoitoriofca@gmail.com',
        max_length=254,
        verbose_name="Correo Remitente (Gmail/Institucional)",
        help_text="Correo desde el cual se enviarán notificaciones, verificaciones y códigos"
    )
    email_host_password = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name="Contraseña de Aplicación (Google App Password)",
        help_text="Contraseña de 16 caracteres generada en Google Account > Seguridad"
    )
    email_remitente_nombre = models.CharField(
        max_length=150,
        default='Repositorio FCA UABC',
        verbose_name="Nombre del Remitente"
    )
    email_host = models.CharField(
        max_length=100,
        default='smtp.gmail.com',
        verbose_name="Servidor SMTP"
    )
    email_port = models.IntegerField(
        default=587,
        verbose_name="Puerto SMTP"
    )
    email_use_tls = models.BooleanField(
        default=True,
        verbose_name="Usar TLS"
    )
    email_use_ssl = models.BooleanField(
        default=False,
        verbose_name="Usar SSL"
    )

    # 2. Configuración de Canales y Contacto Institucional de Soporte
    soporte_email = models.CharField(
        max_length=150,
        default='soporte.fca@uabc.edu.mx',
        verbose_name="Correo de Contacto Institucional"
    )
    soporte_telefono = models.CharField(
        max_length=150,
        default='Ext. Coordinación de Posgrado',
        verbose_name="Teléfono o Extensión"
    )
    soporte_ubicacion = models.CharField(
        max_length=200,
        default='Edificio FCA Campus Tijuana',
        verbose_name="Ubicación Física"
    )
    soporte_tiempo_respuesta = models.CharField(
        max_length=100,
        default='Menos de 24 hrs hábiles',
        verbose_name="Tiempo Estimado de Respuesta"
    )

    # 3. Mensaje Oficial de Bienvenida en el Área de Ayuda
    soporte_bienvenida_titulo = models.CharField(
        max_length=200,
        default='¡Hola! Te damos la bienvenida al Área de Ayuda y Soporte FCA.',
        verbose_name="Título de Bienvenida"
    )
    soporte_bienvenida_cuerpo = models.TextField(
        default='Este canal es atendido directamente por el equipo de Super Administradores (Soporte) de la facultad. A través de este espacio contamos con facultades administrativas completas para:',
        verbose_name="Cuerpo del Mensaje de Bienvenida"
    )
    soporte_facultad_1 = models.CharField(
        max_length=255,
        default='Ver, auditar y validar tus publicaciones o trabajos académicos en PDF.',
        verbose_name="Punto destacado 1"
    )
    soporte_facultad_2 = models.CharField(
        max_length=255,
        default='Modificar y corregir datos de tu ficha docente (nombre oficial, título/grado académico como Dr. o Mtro., nombramiento, universidad de procedencia o número de empleado).',
        verbose_name="Punto destacado 2"
    )
    soporte_facultad_3 = models.CharField(
        max_length=255,
        default='Gestionar incidencias con invitaciones de coautoría, cuentas de usuario o permisos en la plataforma.',
        verbose_name="Punto destacado 3"
    )
    soporte_aviso_final = models.TextField(
        default='Puedes escribirnos con total confianza tu duda o solicitud a continuación. Si necesitas compartirnos un borrador o comprobante, también puedes adjuntarlo libremente aquí. Con gusto te atenderemos.',
        verbose_name="Aviso Final de Bienvenida"
    )

    # 4. Redes Sociales Institucionales (Pie de página)
    footer_facebook = models.CharField(
        max_length=255,
        default='https://www.facebook.com/fcatijuana',
        blank=True,
        verbose_name="Enlace de Facebook"
    )
    footer_instagram = models.CharField(
        max_length=255,
        default='https://www.instagram.com/fca.tij.uabc/',
        blank=True,
        verbose_name="Enlace de Instagram"
    )
    footer_tiktok = models.CharField(
        max_length=255,
        default='https://www.tiktok.com/@fca.tij',
        blank=True,
        verbose_name="Enlace de TikTok"
    )
    footer_youtube = models.CharField(
        max_length=255,
        default='https://www.youtube.com/@FCATijuanaOficial',
        blank=True,
        verbose_name="Enlace de YouTube"
    )
    footer_linkedin = models.CharField(
        max_length=255,
        default='https://www.linkedin.com/in/fcatijuana',
        blank=True,
        verbose_name="Enlace de LinkedIn"
    )

    # 5. Teléfonos y Ubicación del Pie de Página
    footer_telefono_universitario = models.CharField(
        max_length=100,
        default='+52 (664) 979-7500',
        blank=True,
        verbose_name="Línea Universitaria"
    )
    footer_telefono_directo = models.CharField(
        max_length=100,
        default='+52 (664) 683-3174',
        blank=True,
        verbose_name="Línea Directa de la Facultad"
    )
    footer_direccion = models.CharField(
        max_length=255,
        default='Calzada Universidad 14418, Mesa de Otay, Tijuana, B.C., México, C.P. 22427',
        blank=True,
        verbose_name="Dirección Institucional"
    )

    # 6. Enlaces Institucionales del Pie de Página
    footer_link_fca_inicio = models.CharField(
        max_length=255,
        default='https://fca.tij.uabc.mx/',
        blank=True,
        verbose_name="FCA - Inicio"
    )
    footer_link_fca_acerca = models.CharField(
        max_length=255,
        default='https://fca.tij.uabc.mx/acerca-de',
        blank=True,
        verbose_name="FCA - Nuestra Facultad"
    )
    footer_link_estudiantes_ticket = models.CharField(
        max_length=255,
        default='https://fca.tij.uabc.mx/ticketayuda',
        blank=True,
        verbose_name="Estudiantes - Ticket de ayuda (odoo)"
    )
    footer_link_estudiantes_calendario = models.CharField(
        max_length=255,
        default='https://drive.google.com/file/d/1KZwB3fAkZ_88xWOL-iM0gBYVRuFws4oo/view',
        blank=True,
        verbose_name="Estudiantes - Calendario escolar"
    )
    footer_link_docentes_aviso = models.CharField(
        max_length=255,
        default='https://fca.tij.uabc.mx/docentes-infogral',
        blank=True,
        verbose_name="Docentes - Consultar aviso"
    )
    footer_link_institucional_plan = models.CharField(
        max_length=255,
        default='https://fca.tij.uabc.mx/plandedesarrollo',
        blank=True,
        verbose_name="Institucional - Plan de desarrollo 2023-2027"
    )
    footer_link_institucional_paz = models.CharField(
        max_length=255,
        default='https://www.uabc.mx/wp-content/uploads/bsk-pdf-manager/2023/10/Programa-Institucional-para-la-Cultura-de-Paz-UABC_.pdf',
        blank=True,
        verbose_name="Institucional - Programa para la cultura de paz"
    )

    # 7. Personalización de la Página de Contacto (/contacto/)
    contacto_banner_badge = models.CharField(
        max_length=150,
        default='Atención y Vinculación Institucional',
        blank=True,
        verbose_name="Insignia del Banner de Contacto"
    )
    contacto_banner_titulo = models.CharField(
        max_length=200,
        default='Contacto Institucional FCA',
        blank=True,
        verbose_name="Título del Banner de Contacto"
    )
    contacto_banner_subtitulo = models.TextField(
        default='Comunícate directamente con la Facultad de Contaduría y Administración. Nuestro equipo de soporte institucional atenderá tu consulta a la brevedad.',
        blank=True,
        verbose_name="Descripción del Banner de Contacto"
    )
    contacto_form_titulo = models.CharField(
        max_length=150,
        default='Envíanos un mensaje',
        blank=True,
        verbose_name="Título del Formulario de Contacto"
    )
    contacto_form_subtitulo = models.CharField(
        max_length=255,
        default='Llena los campos a continuación y te responderemos a tu correo electrónico institucional o personal.',
        blank=True,
        verbose_name="Subtítulo del Formulario"
    )
    contacto_horario_atencion = models.CharField(
        max_length=150,
        default='Lunes a Viernes de 8:00 AM a 8:00 PM',
        blank=True,
        verbose_name="Horario de Atención"
    )
    contacto_docente_titulo = models.CharField(
        max_length=150,
        default='¿Perteneces al Claustro Docente e Investigadores?',
        blank=True,
        verbose_name="Título Tarjeta Docente"
    )
    contacto_docente_descripcion = models.TextField(
        default='Si eres profesor o investigador de la FCA, inicia sesión con tus credenciales para acceder al Canal Exclusivo de Soporte Interno, auditar tus obras en catálogo o comunicarte con colegas.',
        blank=True,
        verbose_name="Descripción Tarjeta Docente"
    )

    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Actualización")

    class Meta:
        verbose_name = "Configuración del Sistema"
        verbose_name_plural = "Configuraciones del Sistema"

    def __str__(self):
        return f"Configuración General FCA ({self.email_host_user})"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class PreguntaFrecuenteSoporte(models.Model):
    """
    Preguntas frecuentes que se muestran dinámicamente en el panel de soporte para docentes.
    El superadministrador puede añadir, modificar, reordenar o eliminar preguntas.
    """
    pregunta = models.CharField(max_length=255, verbose_name="Pregunta Frecuente")
    respuesta = models.TextField(verbose_name="Respuesta Detallada (admite formato de texto y HTML simple)")
    orden = models.IntegerField(default=0, verbose_name="Orden de Aparición")
    activo = models.BooleanField(default=True, verbose_name="¿Visible para Docentes?")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Pregunta Frecuente de Soporte"
        verbose_name_plural = "Preguntas Frecuentes de Soporte"

    def __str__(self):
        return f"{self.orden}. {self.pregunta}"




class EventoFCA(models.Model):
    """
    Eventos institucionales que se muestran en la página principal ('Próximos Eventos FCA').
    Permite a Soporte añadir fotos, fechas, horarios, ubicaciones y enlaces.
    """
    titulo = models.CharField(max_length=200, verbose_name="Título del Evento")
    fecha = models.DateField(verbose_name="Fecha del Evento")
    horario = models.CharField(max_length=100, default="10:00 AM", verbose_name="Horario (ej: 10:00 AM - 1:00 PM)")
    lugar = models.CharField(max_length=150, default="FCA Campus Tijuana", verbose_name="Lugar del Evento")
    imagen = models.ImageField(upload_to='eventos_fca/', blank=True, null=True, verbose_name="Fotografía o Cartel")
    imagen_url = models.CharField(max_length=500, blank=True, default='', verbose_name="URL de Imagen Externa (Opcional)")
    enlace = models.CharField(max_length=500, blank=True, default='', verbose_name="Enlace de Información o Registro")
    orden = models.IntegerField(default=0, verbose_name="Orden de Visualización")
    activo = models.BooleanField(default=True, verbose_name="¿Visible para el Público?")
    mostrar_si_paso = models.BooleanField(default=True, verbose_name="¿Mostrar en gris cuando ya concluyó?")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        ordering = ['orden', 'fecha', 'id']
        verbose_name = "Próximo Evento FCA"
        verbose_name_plural = "Próximos Eventos FCA"

    def __str__(self):
        return f"{self.titulo} ({self.fecha})"

    @property
    def es_pasado(self):
        if self.fecha:
            from django.utils import timezone
            return self.fecha < timezone.now().date()
        return False

    @property
    def dia_str(self):
        return f"{self.fecha.day:02d}" if self.fecha else "01"

    @property
    def mes_str(self):
        if not self.fecha:
            return "ENE"
        meses = ['ENE', 'FEB', 'MAR', 'ABR', 'MAY', 'JUN', 'JUL', 'AGO', 'SEP', 'OCT', 'NOV', 'DIC']
        return meses[self.fecha.month - 1]

    @property
    def url_imagen(self):
        if self.imagen:
            try:
                return self.imagen.url
            except Exception:
                pass
        if self.imagen_url:
            return self.imagen_url
        return '/static/images/campus_fca.jpg'


class EnlaceRapidoPortal(models.Model):
    """
    Accesos directos que aparecen en la sección 'Enlaces Rápidos e Indexadores' de la página principal.
    Permite modificar enlaces a Gaceta, Sorteos, Fundación, Bibliotecas, o añadir nuevos.
    """
    titulo = models.CharField(max_length=60, verbose_name="Título (ej: GACETA)")
    url = models.CharField(max_length=500, verbose_name="URL de Destino")
    icono = models.CharField(max_length=80, default="fas fa-link", verbose_name="Clase de Icono FontAwesome (ej: fas fa-newspaper)")
    color = models.CharField(max_length=30, default="#006633", verbose_name="Color del Icono o Texto")
    abrir_en_nueva_pestana = models.BooleanField(default=True, verbose_name="¿Abrir en pestaña nueva?")
    orden = models.IntegerField(default=0, verbose_name="Orden de Aparición")
    activo = models.BooleanField(default=True, verbose_name="¿Activo?")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Enlace Rápido del Portal"
        verbose_name_plural = "Enlaces Rápidos del Portal"

    def __str__(self):
        return f"{self.orden}. {self.titulo} -> {self.url}"


class RedSocialFooter(models.Model):
    """
    Iconos y accesos a redes sociales oficiales que aparecen en el pie de página (footer)
    Permite ordenarlas libremente, activar/desactivar o añadir nuevas plataformas.
    """
    nombre = models.CharField(max_length=60, verbose_name="Nombre de la Red (ej: Facebook)")
    url = models.CharField(max_length=500, verbose_name="URL del Perfil")
    icono = models.CharField(max_length=80, default="fab fa-globe", verbose_name="Icono FontAwesome (ej: fab fa-facebook-f)")
    color = models.CharField(max_length=30, default="#006633", verbose_name="Color Distintivo")
    icono_imagen = models.ImageField(upload_to='redes_sociales_footer/', blank=True, null=True, verbose_name="Logotipo o Imagen Personalizada")
    usar_imagen = models.BooleanField(default=False, verbose_name="¿Usar imagen personalizada en vez de icono?")
    filtro_blanco = models.BooleanField(default=False, verbose_name="¿Adaptar a color blanco monocromático institucional?")
    orden = models.IntegerField(default=0, verbose_name="Orden de Aparición")
    activo = models.BooleanField(default=True, verbose_name="¿Activo?")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        ordering = ['orden', 'id']
        verbose_name = "Red Social del Footer"
        verbose_name_plural = "Redes Sociales del Footer"

    def __str__(self):
        return f"{self.orden}. {self.nombre} ({self.url})"


class EnlacePiePagina(models.Model):
    """
    Enlaces y botones de navegación institucional organizados por columnas en el pie de página.
    Permite a Soporte añadir, mover o eliminar enlaces sin tocar el código.
    """
    COLUMNA_CHOICES = [
        ('FCA', 'FCA'),
        ('ESTUDIANTES', 'Estudiantes'),
        ('DOCENTES', 'Docentes'),
        ('INSTITUCIONAL', 'Institucional'),
    ]

    columna = models.CharField(max_length=40, default='FCA', verbose_name="Columna del Footer")
    titulo = models.CharField(max_length=120, verbose_name="Texto del Enlace o Botón")
    url = models.CharField(max_length=500, verbose_name="URL de Destino")
    es_boton = models.BooleanField(default=False, verbose_name="¿Estilo Botón Destacado?")
    abrir_en_nueva_pestana = models.BooleanField(default=True, verbose_name="¿Abrir en pestaña nueva?")
    orden = models.IntegerField(default=0, verbose_name="Orden en la Columna")
    activo = models.BooleanField(default=True, verbose_name="¿Activo?")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        ordering = ['columna', 'orden', 'id']
        verbose_name = "Enlace de Pie de Página"
        verbose_name_plural = "Enlaces de Pie de Página"

    def __str__(self):
        return f"[{self.columna}] {self.orden}. {self.titulo} -> {self.url}"


class MensajeContacto(models.Model):
    """
    Mensajes de contacto recibidos desde el formulario institucional /contacto/.
    Permite registrar y auditar solicitudes de visitantes, estudiantes, docentes y externos,
    asignando folios únicos y permitiendo su seguimiento desde el panel de soporte.
    """
    ESTADO_CHOICES = [
        ('nuevo', 'Nuevo'),
        ('en_proceso', 'En proceso'),
        ('resuelto', 'Resuelto'),
    ]

    folio = models.CharField(max_length=30, unique=True, editable=False, verbose_name="Folio de Seguimiento")
    nombre = models.CharField(max_length=150, verbose_name="Nombre Completo")
    email = models.EmailField(verbose_name="Correo Electrónico")
    telefono = models.CharField(max_length=35, blank=True, verbose_name="Teléfono")
    organizacion = models.CharField(max_length=150, blank=True, verbose_name="Institución / Empresa / Escuela")
    asunto = models.CharField(max_length=200, verbose_name="Asunto")
    mensaje = models.TextField(verbose_name="Mensaje o Pregunta")
    
    # Seguimiento interno de soporte
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='nuevo', verbose_name="Estado de Atención")
    atendido_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='contactos_atendidos', verbose_name="Atendido por"
    )
    notas_soporte = models.TextField(blank=True, verbose_name="Notas internas de soporte")
    respuesta_soporte = models.TextField(blank=True, verbose_name="Respuesta enviada al solicitante")
    fecha_resolucion = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Resolución")
    
    # Auditoría
    ip_origen = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP de Origen")
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Recepción")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Última Modificación")

    class Meta:
        ordering = ['-fecha_creacion']
        verbose_name = "Mensaje de Contacto Web"
        verbose_name_plural = "Mensajes de Contacto Web"

    def __str__(self):
        return f"[{self.folio}] {self.nombre} - {self.asunto} ({self.get_estado_display()})"

    def save(self, *args, **kwargs):
        if not self.folio:
            import datetime, uuid
            ahora = datetime.datetime.now()
            sufijo = uuid.uuid4().hex[:4].upper()
            self.folio = f"FCA-CNT-{ahora.strftime('%Y%m')}-{sufijo}"
            while MensajeContacto.objects.filter(folio=self.folio).exists():
                sufijo = uuid.uuid4().hex[:4].upper()
                self.folio = f"FCA-CNT-{ahora.strftime('%Y%m')}-{sufijo}"
        super().save(*args, **kwargs)
