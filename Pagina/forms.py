"""
====================================================================================================
SISTEMA DE REPOSITORIO ACADÉMICO INSTITUCIONAL (FCA - UABC)
Módulo: Pagina/forms.py
Descripción: Formularios Django para la Carga, Validación y Edición del Acervo Académico.
Autor: Facultad de Contaduría y Administración - Campus Tijuana
====================================================================================================
Este módulo gestiona la capa de validación de datos para la producción científica y académica:
1. Validación Polimórfica de Recursos: Soporta más de 20 tipologías documentales (artículos de revista,
   libros, capítulos, tesis de posgrado, propiedad intelectual IMPI/INDAUTOR, desarrollos tecnológicos,
   transferencia de tecnología, traducciones y dossiers).
2. Seguridad en Subida de Archivos: Limita el peso máximo de los archivos PDF a 20 MB y realiza
   comprobación estricta del tamaño antes de persistir en el almacenamiento.
3. Normalización Dinámica de Metadatos: Resuelve automáticamente catálogos mediante `get_or_create`
   para Áreas de Conocimiento, Entidades Académicas, Tipos de Contenido y asignación de Asesores/Coasesores.
====================================================================================================
"""

from django import forms
from django.core.exceptions import ValidationError
from .models import Articulo, Autor, TipoContenido, Area, Entidad

# Parámetros de seguridad de almacenamiento institucional
LIMITE_MB = 20
LIMITE_BYTES = LIMITE_MB * 1024 * 1024


# ==================================================================================================
# FORMULARIO INSTITUCIONAL DE PRODUCCIÓN ACADÉMICA (ARTICULOFORM)
# ==================================================================================================
class ArticuloForm(forms.ModelForm):
    """
    Formulario integral para el registro y edición de obras en el repositorio institucional.
    Mapea campos transversales (título, resumen, año, autores) y campos especializados según
    la naturaleza del recurso académico.
    """

    # ----------------------------------------------------------------------------------------------
    # Metadatos Principales y Catalogación
    # ----------------------------------------------------------------------------------------------
    autor = forms.ModelMultipleChoiceField(
        queryset=Autor.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Seleccionar Autores"
    )

    tipo_contenido = forms.CharField(
        max_length=100,
        required=True,
        help_text="Tipología del recurso: Artículo, Tesis, Libro, Patente, etc."
    )

    entidad = forms.CharField(
        max_length=100,
        required=True,
        help_text="Unidad académica de adscripción (Facultad, Instituto, Escuela)."
    )

    area = forms.CharField(
        max_length=100,
        required=True,
        help_text="Disciplina o área del conocimiento."
    )

    año_produccion = forms.IntegerField(
        required=True,
        min_value=1900,
        max_value=2026,
        help_text="Año calendario en el que fue publicado o dictaminado el recurso."
    )

    semestre = forms.ChoiceField(
        choices=[
            ('1', '1.er Semestre (Enero - Junio)'),
            ('2', '2.º Semestre (Agosto - Diciembre)'),
        ],
        required=False,
        initial='2',
        label="Semestre Lectivo"
    )

    titulo = forms.CharField(
        max_length=255,
        required=True,
        help_text="Título oficial completo de la obra o documento científico."
    )

    descripcion = forms.CharField(
        widget=forms.Textarea,
        required=True,
        help_text="Resumen ejecutivo, abstracto o síntesis del contenido."
    )

    pdf = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(),
        help_text="Documento a texto completo en formato PDF (máximo 20 MB)."
    )

    # ----------------------------------------------------------------------------------------------
    # Campos Específicos para Publicaciones Periódicas y Revistas Científicas
    # ----------------------------------------------------------------------------------------------
    revista = forms.CharField(max_length=150, required=False)
    isbn_issn = forms.CharField(max_length=50, required=False)
    volumen_numero = forms.CharField(max_length=50, required=False)
    paginas = forms.CharField(max_length=50, required=False)
    doi_enlace = forms.CharField(max_length=255, required=False)

    # ----------------------------------------------------------------------------------------------
    # Campos Específicos para Tesis de Grado y Posgrado
    # ----------------------------------------------------------------------------------------------
    asesor = forms.CharField(max_length=150, required=False)
    coasesor = forms.CharField(max_length=150, required=False)
    grado_academico = forms.CharField(max_length=50, required=False)
    carrera_o_posgrado = forms.CharField(max_length=150, required=False)
    editorial = forms.CharField(max_length=150, required=False)
    palabras_clave = forms.CharField(max_length=255, required=False)
    idioma = forms.CharField(max_length=50, required=False)

    # ----------------------------------------------------------------------------------------------
    # Campos de Propiedad Intelectual e Industrial (INDAUTOR / IMPI)
    # ----------------------------------------------------------------------------------------------
    tipo_proteccion = forms.CharField(max_length=150, required=False)
    numero_registro = forms.CharField(max_length=150, required=False)
    rama_propiedad = forms.CharField(max_length=150, required=False)
    titular_propiedad = forms.CharField(max_length=255, required=False)
    rol_participacion = forms.CharField(max_length=100, required=False)
    ambito_solicitud = forms.CharField(max_length=50, required=False)
    fecha_expedicion_solicitud = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    estado_propiedad = forms.CharField(max_length=50, required=False)
    solicitud_internacional_numero = forms.CharField(max_length=150, required=False)
    publicacion_internacional_numero = forms.CharField(max_length=150, required=False)

    # ----------------------------------------------------------------------------------------------
    # Campos de Innovación y Desarrollo Tecnológico
    # ----------------------------------------------------------------------------------------------
    tipo_desarrollo = forms.CharField(max_length=150, required=False)
    problema_atiende = forms.CharField(required=False, widget=forms.Textarea)
    beneficiarios_impacto = forms.CharField(required=False, widget=forms.Textarea)

    # ----------------------------------------------------------------------------------------------
    # Campos de Transferencia Tecnológica y Vinculación
    # ----------------------------------------------------------------------------------------------
    institucion_receptora = forms.CharField(max_length=255, required=False)
    tipo_transferencia = forms.CharField(max_length=150, required=False)

    # ----------------------------------------------------------------------------------------------
    # Campos de Traducción Científica y Humanística
    # ----------------------------------------------------------------------------------------------
    idioma_original = forms.CharField(max_length=100, required=False)
    titulo_original = forms.CharField(max_length=255, required=False)
    autor_original = forms.CharField(max_length=255, required=False)

    # ----------------------------------------------------------------------------------------------
    # Campos de Compilación, Dossier, Prólogo y Reportes de Investigación
    # ----------------------------------------------------------------------------------------------
    nombre_compilador_coordinador = forms.CharField(max_length=255, required=False)
    obra_receptora = forms.CharField(max_length=255, required=False)
    proyecto_origen = forms.CharField(max_length=255, required=False)

    class Meta:
        model = Articulo
        # Se excluyen campos gobernados exclusivamente por el flujo de moderación o la sesión activa
        exclude = ['estado', 'motivo_rechazo', 'subido_por']

    def __init__(self, *args, **kwargs):
        """
        Inicializa el formulario precargando los valores existentes en caso de edición de una obra.
        """
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.tipo_contenido:
                self.initial['tipo_contenido'] = self.instance.tipo_contenido.nombre
            if self.instance.entidad:
                self.initial['entidad'] = self.instance.entidad.nombre
            if self.instance.area:
                self.initial['area'] = self.instance.area.nombre

            # Precarga de métricas editoriales
            self.fields['revista'].initial = self.instance.revista
            self.fields['isbn_issn'].initial = self.instance.isbn_issn
            self.fields['volumen_numero'].initial = self.instance.volumen_numero
            self.fields['paginas'].initial = self.instance.paginas
            self.fields['doi_enlace'].initial = self.instance.doi_enlace

            # Precarga de datos de grado y dirección de tesis
            if self.instance.asesor:
                nombre_asesor = getattr(self.instance.asesor, 'nombre', str(self.instance.asesor))
                self.initial['asesor'] = nombre_asesor
                self.fields['asesor'].initial = nombre_asesor

            if self.instance.coasesor:
                nombre_coasesor = getattr(self.instance.coasesor, 'nombre', str(self.instance.coasesor))
                self.initial['coasesor'] = nombre_coasesor
                self.fields['coasesor'].initial = nombre_coasesor

            self.fields['grado_academico'].initial = self.instance.grado_academico
            self.fields['carrera_o_posgrado'].initial = self.instance.carrera_o_posgrado
            self.fields['editorial'].initial = self.instance.editorial
            self.fields['palabras_clave'].initial = self.instance.palabras_clave
            if hasattr(self.instance, 'semestre') and self.instance.semestre:
                self.fields['semestre'].initial = self.instance.semestre
            self.fields['idioma'].initial = self.instance.idioma

            # Precarga de patentes y propiedad intelectual
            self.fields['tipo_proteccion'].initial = self.instance.tipo_proteccion
            self.fields['numero_registro'].initial = self.instance.numero_registro
            self.fields['rama_propiedad'].initial = self.instance.rama_propiedad
            self.fields['titular_propiedad'].initial = self.instance.titular_propiedad
            self.fields['rol_participacion'].initial = self.instance.rol_participacion
            self.fields['ambito_solicitud'].initial = self.instance.ambito_solicitud
            if self.instance.fecha_expedicion_solicitud:
                self.fields['fecha_expedicion_solicitud'].initial = self.instance.fecha_expedicion_solicitud.strftime('%Y-%m-%d')
            self.fields['estado_propiedad'].initial = self.instance.estado_propiedad
            self.fields['solicitud_internacional_numero'].initial = self.instance.solicitud_internacional_numero
            self.fields['publicacion_internacional_numero'].initial = self.instance.publicacion_internacional_numero

            # Precarga de desarrollo tecnológico e impacto social
            self.fields['tipo_desarrollo'].initial = self.instance.tipo_desarrollo
            self.fields['problema_atiende'].initial = self.instance.problema_atiende
            self.fields['beneficiarios_impacto'].initial = self.instance.beneficiarios_impacto

            # Precarga de vinculación institucional
            self.fields['institucion_receptora'].initial = self.instance.institucion_receptora
            self.fields['tipo_transferencia'].initial = self.instance.tipo_transferencia

            # Precarga de traducciones
            self.fields['idioma_original'].initial = self.instance.idioma_original
            self.fields['titulo_original'].initial = self.instance.titulo_original
            self.fields['autor_original'].initial = self.instance.autor_original

            # Precarga de compilaciones y proyectos de investigación
            self.fields['nombre_compilador_coordinador'].initial = self.instance.nombre_compilador_coordinador
            self.fields['obra_receptora'].initial = self.instance.obra_receptora
            self.fields['proyecto_origen'].initial = self.instance.proyecto_origen

    # ----------------------------------------------------------------------------------------------
    # Métodos de Limpieza y Validación Sanitaria de Datos
    # ----------------------------------------------------------------------------------------------
    def clean_pdf(self):
        """Valida que el archivo digital adjunto no sobrepase el umbral de 20 MB."""
        archivo = self.cleaned_data.get('pdf')
        if archivo and hasattr(archivo, 'size') and archivo.size > LIMITE_BYTES:
            tamano_mb = round(archivo.size / (1024 * 1024), 2)
            raise ValidationError(
                f"El archivo PDF excede el límite permitido ({LIMITE_MB} MB). Pesa {tamano_mb} MB."
            )
        return archivo

    def clean_tipo_contenido(self):
        """Normaliza el tipo de contenido y obtiene o crea la instancia correspondiente."""
        nombre = self.cleaned_data.get('tipo_contenido', '').strip()
        tipo, _ = TipoContenido.objects.get_or_create(nombre=nombre)
        return tipo

    def clean_area(self):
        """Normaliza el área disciplinar y obtiene o crea la instancia correspondiente."""
        nombre = self.cleaned_data.get('area', '').strip()
        area, _ = Area.objects.get_or_create(nombre=nombre)
        return area

    def clean_entidad(self):
        """Normaliza la entidad académica universitaria y obtiene o crea la instancia."""
        nombre = self.cleaned_data.get('entidad', '').strip()
        entidad, _ = Entidad.objects.get_or_create(nombre=nombre)
        return entidad

    def clean_grado_academico(self):
        """Estandariza los nombres canónicos de los grados académicos (sin acentos en claves)."""
        grado = self.cleaned_data.get('grado_academico', '')
        if isinstance(grado, str):
            grado = grado.strip()
            if grado.lower() in ['maestría', 'maestria']:
                return 'Maestria'
            elif grado.lower() in ['doctorado']:
                return 'Doctorado'
            elif grado.lower() in ['licenciatura']:
                return 'Licenciatura'
            elif grado.lower() in ['especialidad']:
                return 'Especialidad'
        return grado

    def clean_asesor(self):
        """Busca al asesor en el catálogo de autores institucionales o lo registra automáticamente."""
        nombre = self.cleaned_data.get('asesor', '')
        if isinstance(nombre, str):
            nombre = nombre.strip()
        if not nombre:
            return None
        autor, _ = Autor.objects.get_or_create(
            nombre=nombre,
            defaults={'institucion_origen': 'UABC'}
        )
        return autor

    def clean_coasesor(self):
        """Busca al coasesor en el catálogo de autores institucionales o lo registra automáticamente."""
        nombre = self.cleaned_data.get('coasesor', '')
        if isinstance(nombre, str):
            nombre = nombre.strip()
        if not nombre:
            return None
        autor, _ = Autor.objects.get_or_create(
            nombre=nombre,
            defaults={'institucion_origen': 'UABC'}
        )
        return autor

    def save(self, commit=True):
        """
        Persiste los datos normalizados y actualiza las relaciones Many-to-Many de autores.
        """
        articulo = super().save(commit=False)

        # Asignación de campos de revistas y publicaciones
        articulo.revista = self.cleaned_data.get('revista', '')
        articulo.isbn_issn = self.cleaned_data.get('isbn_issn', '')
        articulo.volumen_numero = self.cleaned_data.get('volumen_numero', '')
        articulo.paginas = self.cleaned_data.get('paginas', '')
        articulo.doi_enlace = self.cleaned_data.get('doi_enlace', '')

        # Asignación de dirección académica
        articulo.asesor = self.cleaned_data.get('asesor')
        articulo.coasesor = self.cleaned_data.get('coasesor')
        articulo.grado_academico = self.cleaned_data.get('grado_academico', '')
        articulo.carrera_o_posgrado = self.cleaned_data.get('carrera_o_posgrado', '')
        articulo.editorial = self.cleaned_data.get('editorial', '')
        articulo.palabras_clave = self.cleaned_data.get('palabras_clave', '')
        articulo.idioma = self.cleaned_data.get('idioma', '')

        # Asignación de propiedad intelectual
        articulo.tipo_proteccion = self.cleaned_data.get('tipo_proteccion', '')
        articulo.numero_registro = self.cleaned_data.get('numero_registro', '')
        articulo.rama_propiedad = self.cleaned_data.get('rama_propiedad', '')
        articulo.titular_propiedad = self.cleaned_data.get('titular_propiedad', '')
        articulo.rol_participacion = self.cleaned_data.get('rol_participacion', '')
        articulo.ambito_solicitud = self.cleaned_data.get('ambito_solicitud', '')
        articulo.fecha_expedicion_solicitud = self.cleaned_data.get('fecha_expedicion_solicitud')
        articulo.estado_propiedad = self.cleaned_data.get('estado_propiedad', '')
        articulo.solicitud_internacional_numero = self.cleaned_data.get('solicitud_internacional_numero', '')
        articulo.publicacion_internacional_numero = self.cleaned_data.get('publicacion_internacional_numero', '')

        # Asignación de innovación y tecnología
        articulo.tipo_desarrollo = self.cleaned_data.get('tipo_desarrollo', '')
        articulo.problema_atiende = self.cleaned_data.get('problema_atiende', '')
        articulo.beneficiarios_impacto = self.cleaned_data.get('beneficiarios_impacto', '')

        # Asignación de transferencia tecnológica
        articulo.institucion_receptora = self.cleaned_data.get('institucion_receptora', '')
        articulo.tipo_transferencia = self.cleaned_data.get('tipo_transferencia', '')

        # Asignación de traducciones
        articulo.idioma_original = self.cleaned_data.get('idioma_original', '')
        articulo.titulo_original = self.cleaned_data.get('titulo_original', '')
        articulo.autor_original = self.cleaned_data.get('autor_original', '')

        # Asignación de obras compuestas y proyectos
        articulo.nombre_compilador_coordinador = self.cleaned_data.get('nombre_compilador_coordinador', '')
        articulo.obra_receptora = self.cleaned_data.get('obra_receptora', '')
        articulo.proyecto_origen = self.cleaned_data.get('proyecto_origen', '')

        if commit:
            articulo.save()
            if self.cleaned_data.get('autor'):
                articulo.autor.set(self.cleaned_data['autor'])
        return articulo
