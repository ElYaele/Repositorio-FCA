from django import forms
from django.core.exceptions import ValidationError
from .models import Articulo, Autor, TipoContenido, Area, Entidad

LIMITE_MB = 20
LIMITE_BYTES = LIMITE_MB * 1024 * 1024


class ArticuloForm(forms.ModelForm):
    autor = forms.ModelMultipleChoiceField(
        queryset=Autor.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Seleccionar Autores"
    )

    tipo_contenido = forms.CharField(
        max_length=100,
        required=True
    )

    entidad = forms.CharField(
        max_length=100,
        required=True
    )

    area = forms.CharField(
        max_length=100,
        required=True
    )

    año_produccion = forms.IntegerField(
        required=True,
        min_value=1900,
        max_value=2026
    )

    titulo = forms.CharField(
        max_length=255,
        required=True
    )

    descripcion = forms.CharField(
        widget=forms.Textarea,
        required=True
    )

    pdf = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput()
    )

    # Campos específicos alineados a los nombres reales del modelo
    revista = forms.CharField(max_length=150, required=False)
    isbn_issn = forms.CharField(max_length=50, required=False)
    volumen_numero = forms.CharField(max_length=50, required=False)
    paginas = forms.CharField(max_length=50, required=False)
    doi_enlace = forms.CharField(max_length=255, required=False)

    # Campos de Tesis, Libros y otros recursos
    asesor = forms.CharField(max_length=150, required=False)
    grado_academico = forms.CharField(max_length=50, required=False)
    carrera_o_posgrado = forms.CharField(max_length=150, required=False)
    editorial = forms.CharField(max_length=150, required=False)
    palabras_clave = forms.CharField(max_length=255, required=False)
    idioma = forms.CharField(max_length=50, required=False)

    class Meta:
        model = Articulo
        exclude = ['estado', 'motivo_rechazo', 'subido_por']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.tipo_contenido:
                self.initial['tipo_contenido'] = self.instance.tipo_contenido.nombre
            if self.instance.entidad:
                self.initial['entidad'] = self.instance.entidad.nombre
            if self.instance.area:
                self.initial['area'] = self.instance.area.nombre

            # Precargamos los campos específicos en la edición
            self.fields['revista'].initial = self.instance.revista
            self.fields['isbn_issn'].initial = self.instance.isbn_issn
            self.fields['volumen_numero'].initial = self.instance.volumen_numero
            self.fields['paginas'].initial = self.instance.paginas
            self.fields['doi_enlace'].initial = self.instance.doi_enlace

            # Precargamos los campos de Tesis, Libros y generales
            if self.instance.asesor:
                nombre_asesor = getattr(self.instance.asesor, 'nombre', str(self.instance.asesor))
                self.initial['asesor'] = nombre_asesor
                self.fields['asesor'].initial = nombre_asesor

            self.fields['grado_academico'].initial = self.instance.grado_academico
            self.fields['carrera_o_posgrado'].initial = self.instance.carrera_o_posgrado
            self.fields['editorial'].initial = self.instance.editorial
            self.fields['palabras_clave'].initial = self.instance.palabras_clave
            self.fields['idioma'].initial = self.instance.idioma

    def clean_pdf(self):
        archivo = self.cleaned_data.get('pdf')
        if archivo and hasattr(archivo, 'size') and archivo.size > LIMITE_BYTES:
            tamano_mb = round(archivo.size / (1024 * 1024), 2)
            raise ValidationError(
                f"El archivo PDF excede el límite permitido ({LIMITE_MB} MB). Pesa {tamano_mb} MB."
            )
        return archivo

    def clean_tipo_contenido(self):
        nombre = self.cleaned_data.get('tipo_contenido', '').strip()
        tipo, _ = TipoContenido.objects.get_or_create(nombre=nombre)
        return tipo

    def clean_area(self):
        nombre = self.cleaned_data.get('area', '').strip()
        area, _ = Area.objects.get_or_create(nombre=nombre)
        return area

    def clean_entidad(self):
        nombre = self.cleaned_data.get('entidad', '').strip()
        entidad, _ = Entidad.objects.get_or_create(nombre=nombre)
        return entidad

    def clean_asesor(self):
        nombre = self.cleaned_data.get('asesor', '')
        if isinstance(nombre, str):
            nombre = nombre.strip()
        if not nombre:
            return None
        # Busca al asesor en el catálogo de autores o lo crea automáticamente
        autor, _ = Autor.objects.get_or_create(
            nombre=nombre,
            defaults={'institucion_origen': 'UABC'}
        )
        return autor

    def save(self, commit=True):
        articulo = super().save(commit=False)

        # Asignamos los campos a las columnas del modelo
        articulo.revista = self.cleaned_data.get('revista', '')
        articulo.isbn_issn = self.cleaned_data.get('isbn_issn', '')
        articulo.volumen_numero = self.cleaned_data.get('volumen_numero', '')
        articulo.paginas = self.cleaned_data.get('paginas', '')
        articulo.doi_enlace = self.cleaned_data.get('doi_enlace', '')

        # Asignamos la instancia de Autor o None según la limpieza
        articulo.asesor = self.cleaned_data.get('asesor')
        articulo.grado_academico = self.cleaned_data.get('grado_academico', '')
        articulo.carrera_o_posgrado = self.cleaned_data.get('carrera_o_posgrado', '')
        articulo.editorial = self.cleaned_data.get('editorial', '')
        articulo.palabras_clave = self.cleaned_data.get('palabras_clave', '')
        articulo.idioma = self.cleaned_data.get('idioma', '')

        if commit:
            articulo.save()
            if self.cleaned_data.get('autor'):
                articulo.autor.set(self.cleaned_data['autor'])
        return articulo