import re
from datetime import timedelta, date, datetime
from django.utils import timezone
from django.views.generic import ListView, TemplateView, CreateView, UpdateView
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator  # <--- Agregado para Paginación

from .models import (
    Articulo, Entidad, Area, TipoContenido, Autor, MensajeCumpleanos,
    Nombramiento, EnlaceProfesional, RegistroAuditoria, Universidad
)
from .forms import ArticuloForm


def es_superusuario(user):
    return user.is_authenticated and user.is_superuser


def es_superusuario_principal(user):
    return user.is_authenticated and (user.username.lower() == 'yaele' or user.id == 1)


def filtro_publico_articulos():
    return Q(estado='aprobado')


def registrar_auditoria(usuario, accion, detalle=""):
    """Registra una acción administrativa en el buzón de auditoría."""
    RegistroAuditoria.objects.create(
        admin_usuario=usuario if usuario and usuario.is_authenticated else None,
        accion=accion,
        detalle=detalle
    )


def obtener_autores_activos_catalogo():
    return Autor.objects.filter(
        es_profesor=True
    ).exclude(
        usuario__is_superuser=True
    ).distinct().order_by('nombre')


def limpiar_autores_huerfanos():
    Autor.objects.filter(usuario__isnull=True, documentos__isnull=True).delete()


def obtener_idiomas_unicos():
    """Función auxiliar para unificar idiomas base y de la base de datos sin duplicados."""
    idiomas_base = ["Español", "Inglés", "Francés", "Portugués", "Alemán", "Italiano", "Chino Mandarín", "Japonés",
                    "Hindi"]
    idiomas_raw = Articulo.objects.exclude(idioma__isnull=True).exclude(idioma__exact='').values_list('idioma',
                                                                                                      flat=True)
    idiomas_db = [lang.strip().title() for lang in idiomas_raw if lang and lang.strip()]
    return sorted(list(set(idiomas_base + idiomas_db)))


def obtener_o_sincronizar_universidades():
    """
    Sincroniza y retorna el catálogo global de universidades.
    Si existen autores externos con 'institucion_origen' que aún no estén
    registrados en la tabla Universidad, los detecta, extrae su nombre y siglas,
    y los incorpora automáticamente al catálogo.
    """
    autores_externos = Autor.objects.exclude(
        institucion_origen__isnull=True
    ).exclude(
        institucion_origen__exact=''
    ).exclude(
        institucion_origen__iexact='UABC'
    )
    for autor in autores_externos:
        texto = autor.institucion_origen.strip()
        match = re.search(r'^(.*?)\s*\(([^()]+)\)$', texto)
        if match:
            nom = match.group(1).strip()
            sig = match.group(2).strip().upper()
        else:
            nom = texto
            sig = "".join([p[0].upper() for p in nom.split() if p.isalpha() and len(p) > 2])[:10]
        if nom:
            Universidad.objects.get_or_create(
                nombre__iexact=nom,
                defaults={'nombre': nom, 'siglas': sig}
            )
    return Universidad.objects.all().order_by('nombre')


# ==============================================================================
# VISTAS PRINCIPALES DEL REPOSITORIO
# ==============================================================================

class HomePageView(TemplateView):
    template_name = "Base.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        articulos_visibles = Articulo.objects.filter(filtro_publico_articulos())

        context['total_documentos'] = articulos_visibles.count()
        context['autores'] = obtener_autores_activos_catalogo()

        context['entidades'] = Entidad.objects.filter(articulo__in=articulos_visibles).annotate(
            total=Count('articulo', filter=Q(articulo__estado='aprobado'))).distinct()
        context['anos_produccion'] = articulos_visibles.exclude(año_produccion__isnull=True).values(
            'año_produccion').annotate(total=Count('id')).order_by('-año_produccion')
        context['tipos_contenido'] = TipoContenido.objects.filter(articulo__in=articulos_visibles).annotate(
            total=Count('articulo', filter=Q(articulo__estado='aprobado'))).distinct()
        context['areas'] = Area.objects.filter(articulo__in=articulos_visibles).annotate(
            total=Count('articulo', filter=Q(articulo__estado='aprobado'))).distinct()
        context['idiomas_existentes'] = articulos_visibles.exclude(idioma__isnull=True).exclude(
            idioma__exact='').values('idioma').annotate(total=Count('id')).order_by('idioma')
        context['revistas_existentes'] = articulos_visibles.exclude(revista__isnull=True).exclude(
            revista__exact='').values('revista').annotate(total=Count('id')).order_by('revista')

        # <--- MEJORA 3: MÉTRICAS GLOBALES --->
        context['total_obras'] = context['total_documentos']
        context['investigadores_claustro'] = Autor.objects.filter(es_profesor=True).count()
        context['universidades_aliadas'] = Universidad.objects.count()

        return context


@method_decorator(user_passes_test(lambda u: u.is_authenticated and (u.is_superuser or u.is_staff)), name='dispatch')
class ArticuloCreateView(CreateView):
    model = Articulo
    form_class = ArticuloForm
    template_name = 'Formulario.html'
    success_url = reverse_lazy('mi_panel')

    def form_valid(self, form):
        articulo = form.save(commit=False)
        if articulo.idioma:
            articulo.idioma = articulo.idioma.strip().title()
        articulo.subido_por = self.request.user
        articulo.estado = 'aprobado' if self.request.user.is_superuser else 'pendiente'
        articulo.save()
        form.save_m2m()
        registrar_auditoria(self.request.user, "Subida de Obra", f"Subió la obra: {articulo.titulo}")
        return redirect('mi_panel')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['autores'] = obtener_autores_activos_catalogo()
        context['tipos_contenido'] = TipoContenido.objects.all()
        context['areas'] = Area.objects.all()
        context['idiomas_existentes'] = obtener_idiomas_unicos()
        context['universidades'] = obtener_o_sincronizar_universidades()
        return context


@method_decorator(login_required, name='dispatch')
class ArticuloDocenteEditarView(UpdateView):
    model = Articulo
    form_class = ArticuloForm
    template_name = 'Formulario.html'

    def dispatch(self, request, *args, **kwargs):
        articulo = self.get_object()
        if not (request.user.is_superuser or articulo.subido_por == request.user):
            return HttpResponseForbidden("No tienes autorización para editar esta obra.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        articulo = form.save(commit=False)
        if articulo.idioma:
            articulo.idioma = articulo.idioma.strip().title()

        if articulo.estado == 'rechazado' and not self.request.user.is_superuser:
            articulo.estado = 'pendiente'
            articulo.motivo_rechazo = ''
            articulo.moderado_por = None
            messages.info(self.request, "Has reenviado la obra corregida. Quedará en espera de revisión.")
            registrar_auditoria(self.request.user, "Reenvío de Obra Corregida", f"Reenvió la obra: {articulo.titulo}")
        else:
            messages.success(self.request, "Los cambios en la obra han sido guardados exitosamente.")
            registrar_auditoria(self.request.user, "Edición de Obra", f"Modificó la obra: {articulo.titulo}")
        articulo.save()
        form.save_m2m()
        return redirect(self.get_success_url())

    def get_success_url(self):
        if self.request.user.is_superuser:
            return reverse('panel_usuarios')
        return reverse('mi_panel')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['autores'] = obtener_autores_activos_catalogo()
        context['tipos_contenido'] = TipoContenido.objects.all()
        context['areas'] = Area.objects.all()
        context['es_edicion'] = True
        context['autores_asignados'] = self.object.autor.all()
        context['idiomas_existentes'] = obtener_idiomas_unicos()
        context['motivo_rechazo'] = self.object.motivo_rechazo if self.object else ''
        context['universidades'] = obtener_o_sincronizar_universidades()
        return context


class BusquedaResultadosView(ListView):
    model = Articulo
    template_name = 'Resultados.html'
    context_object_name = 'articulos'
    paginate_by = 15  # <--- MEJORA 2: Paginación de 15 en 15

    def get_queryset(self):
        q = self.request.GET.get('q', '').strip()
        tipo_id = self.request.GET.get('tipo', '').strip()
        entidad_id = self.request.GET.get('entidad', '').strip()
        area_filtro = self.request.GET.get('area', '').strip()
        anio_filtro = self.request.GET.get('anio', '').strip()
        filtro_atributo = self.request.GET.get('filtro_atributo', 'todo').strip().lower()  # <--- MEJORA 4

        resultados = Articulo.objects.filter(filtro_publico_articulos()).prefetch_related(
            'autor', 'tipo_contenido', 'area', 'entidad'
        )

        if q:
            # <--- MEJORA 4: Buscador Avanzado --->
            if filtro_atributo == 'titulos':
                resultados = resultados.filter(titulo__icontains=q)
            elif filtro_atributo == 'autores':
                resultados = resultados.filter(autor__nombre__icontains=q)
            elif filtro_atributo == 'areas':
                resultados = resultados.filter(area__nombre__icontains=q)
            else:  # 'todo'
                resultados = resultados.filter(
                    Q(titulo__icontains=q) |
                    Q(descripcion__icontains=q) |
                    Q(autor__nombre__icontains=q) |
                    Q(tipo_contenido__nombre__icontains=q) |
                    Q(area__nombre__icontains=q) |
                    Q(idioma__icontains=q) |
                    Q(palabras_clave__icontains=q) |
                    Q(autor__institucion_origen__icontains=q)
                )

        if tipo_id:
            resultados = resultados.filter(tipo_contenido_id=tipo_id)
        if entidad_id:
            resultados = resultados.filter(entidad_id=entidad_id)
        if area_filtro:
            if area_filtro.isdigit():
                resultados = resultados.filter(area_id=area_filtro)
            else:
                resultados = resultados.filter(area__nombre__iexact=area_filtro)
        if anio_filtro:
            resultados = resultados.filter(año_produccion=anio_filtro)

        # Se agrega order_by para garantizar el funcionamiento correcto de la paginación
        return resultados.distinct().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        articulos_aprobados = Articulo.objects.filter(filtro_publico_articulos())

        context['tipos_contenido'] = TipoContenido.objects.filter(articulo__in=articulos_aprobados).annotate(
            total=Count('articulo', filter=Q(articulo__estado='aprobado'))
        ).distinct()

        context['entidades'] = Entidad.objects.filter(articulo__in=articulos_aprobados).annotate(
            total=Count('articulo', filter=Q(articulo__estado='aprobado'))
        ).distinct()

        context['areas_disponibles'] = Area.objects.filter(articulo__in=articulos_aprobados).annotate(
            total=Count('articulo', filter=Q(articulo__estado='aprobado'))
        ).distinct()

        context['anios_disponibles'] = articulos_aprobados.exclude(año_produccion__isnull=True).values(
            'año_produccion').annotate(
            total=Count('id')
        ).order_by('-año_produccion')

        context['query_actual'] = self.request.GET.get('q', '')
        context['tipo_actual'] = self.request.GET.get('tipo', '')
        context['entidad_actual'] = self.request.GET.get('entidad', '')
        context['area_actual'] = self.request.GET.get('area', '')
        context['anio_actual'] = self.request.GET.get('anio', '')
        context['filtro_atributo_actual'] = self.request.GET.get('filtro_atributo', 'todo')  # <--- MEJORA 4

        context['total_documentos'] = articulos_aprobados.count()

        # Como usamos paginación, el queryset real total es la cuenta del paginator
        context['resultados_count'] = self.get_queryset().count()
        return context


# ==============================================================================
# AUTENTICACIÓN Y REGISTRO
# ==============================================================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, 'Tu cuenta está inactiva o suspendida.')
                return render(request, 'login.html', {'form': form})
            login(request, user)
            return redirect('/')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('/')


def solicitar_registro_view(request):
    if request.method == 'POST':
        tipo_personal = request.POST.get('tipo_personal', 'docente')
        nombre = request.POST.get('nombre', '').strip()
        username = request.POST.get('username', '').strip()
        correo = request.POST.get('correo', '').strip()
        password = request.POST.get('password')
        fecha_nacimiento = request.POST.get('fecha_nacimiento')
        genero = request.POST.get('genero', 'NE')
        numero_empleado = request.POST.get('numero_empleado', '').strip()

        institucion_final = "UABC"
        es_profesor = (tipo_personal in ['docente', 'externo'])
        es_externo = (tipo_personal == 'externo')

        if es_externo:
            inst_sel = request.POST.get('institucion_existente', 'nueva').strip()
            if inst_sel != 'nueva' and inst_sel:
                institucion_final = inst_sel
            else:
                nom_uni = request.POST.get('institucion_nombre', '').strip()
                sig_uni = request.POST.get('institucion_siglas', '').strip().upper()
                if nom_uni and sig_uni:
                    institucion_final = f"{nom_uni} ({sig_uni})"
                    Universidad.objects.get_or_create(
                        nombre__iexact=nom_uni,
                        defaults={'nombre': nom_uni, 'siglas': sig_uni}
                    )
                elif nom_uni:
                    institucion_final = nom_uni

        if User.objects.filter(username=username).exists():
            messages.error(request, 'El nombre de usuario ya está registrado.')
        elif User.objects.filter(email=correo).exists():
            messages.error(request, 'El correo electrónico ya está registrado.')
        else:
            user = User.objects.create_user(username=username, email=correo, password=password)
            user.is_active = False
            user.is_staff = True
            user.save()

            Autor.objects.create(
                usuario=user,
                nombre=nombre if nombre else username,
                correo=correo,
                institucion_origen=institucion_final,
                fecha_nacimiento=fecha_nacimiento if fecha_nacimiento else None,
                genero=genero,
                numero_empleado=numero_empleado if numero_empleado else None,
                es_profesor=es_profesor,
                es_externo=es_externo,
                estado_semblanza='borrador' if es_profesor else 'aprobado'
            )

            registrar_auditoria(None, "Solicitud de Cuenta",
                                f"Nueva solicitud de registro: {username} ({correo}) - Institución: {institucion_final}")
            messages.success(request, 'Solicitud enviada exitosamente. Tu cuenta será revisada por el administrador.')
            return redirect('login')

    unis = obtener_o_sincronizar_universidades()
    return render(request, 'solicitar_registro.html', {'universidades': unis})


# ==============================================================================
# PANEL PROPIO DEL DOCENTE / ACTUALIZAR PERFIL
# ==============================================================================

@login_required
def mi_panel_view(request):
    # <--- MEJORA 2: Paginación en Paneles --->
    mis_subidas_qs = Articulo.objects.filter(subido_por=request.user).order_by('-created_at')
    paginator_subidas = Paginator(mis_subidas_qs, 15)
    page_subidas = request.GET.get('page_subidas')
    mis_subidas = paginator_subidas.get_page(page_subidas)

    mis_coautorias_qs = Articulo.objects.filter(autor__usuario=request.user).exclude(
        subido_por=request.user).distinct().order_by('-created_at')
    paginator_coautorias = Paginator(mis_coautorias_qs, 15)
    page_coautorias = request.GET.get('page_coautorias')
    mis_coautorias = paginator_coautorias.get_page(page_coautorias)

    # Obtención de felicitaciones si el usuario tiene perfil Autor
    mensajes_cumpleanos = []
    es_mi_cumpleanos = False
    if hasattr(request.user, 'autor') and request.user.autor:
        mensajes_cumpleanos = request.user.autor.mensajes_recibidos.all().order_by('-fecha_envio')
        es_mi_cumpleanos = request.user.autor.es_cumpleanos_hoy

    # Detección de colegas docentes que cumplen años hoy (excluyendo al usuario actual)
    hoy = timezone.localdate()
    cumpleaneros_qs = Autor.objects.filter(
        es_profesor=True,
        fecha_nacimiento__isnull=False,
        fecha_nacimiento__day=hoy.day,
        fecha_nacimiento__month=hoy.month
    )
    if hasattr(request.user, 'autor') and request.user.autor:
        cumpleaneros_qs = cumpleaneros_qs.exclude(id=request.user.autor.id)

    cumpleaneros_hoy = list(cumpleaneros_qs)

    # Respaldo en Python si la base de datos no evaluó los filtros __day y __month
    if not cumpleaneros_hoy:
        todos_profes = Autor.objects.filter(es_profesor=True, fecha_nacimiento__isnull=False)
        if hasattr(request.user, 'autor') and request.user.autor:
            todos_profes = todos_profes.exclude(id=request.user.autor.id)
        cumpleaneros_hoy = [p for p in todos_profes if getattr(p, 'es_cumpleanos_hoy', False)]

    context = {
        'mis_subidas': mis_subidas,
        'mis_coautorias': mis_coautorias,
        'total_aprobadas': mis_subidas_qs.filter(estado='aprobado').count(),
        'total_pendientes': mis_subidas_qs.filter(estado='pendiente').count(),
        'total_rechazadas': mis_subidas_qs.filter(estado='rechazado').count(),
        'password_form': PasswordChangeForm(request.user),
        'mensajes_cumpleanos': mensajes_cumpleanos,
        'es_mi_cumpleanos': es_mi_cumpleanos,
        'cumpleaneros_hoy': cumpleaneros_hoy,
    }
    return render(request, 'mi_panel.html', context)


@login_required
def actualizar_perfil_docente_view(request):
    if request.method == 'POST':
        if hasattr(request.user, 'autor'):
            autor = request.user.autor
        else:
            nombre_temp = request.POST.get('nombre', '').strip()
            autor = Autor.objects.filter(nombre__iexact=nombre_temp).first()
            if not autor:
                autor = Autor.objects.create(usuario=request.user, nombre=nombre_temp or request.user.username)
            else:
                autor.usuario = request.user

        foto_personal_subida = request.FILES.get('foto_personal')
        if foto_personal_subida and 'nombre' not in request.POST:
            autor.foto_personal = foto_personal_subida
            autor.save()
            messages.success(request, 'Tu foto de perfil personal ha sido actualizada.')
            return redirect('mi_panel')

        nombre = request.POST.get('nombre', '').strip()
        genero = request.POST.get('genero', 'NE')
        genero_otro = request.POST.get('genero_otro', '').strip()
        cargos_seleccionados = request.POST.getlist('roles_facultad')

        biografia = request.POST.get('biografia', '').strip()
        # Semblanza enriquecida generada por Quill.js (mantiene etiquetas HTML)
        biografia_extendida = request.POST.get('biografia_extendida', '').strip()
        orcid = request.POST.get('orcid', '').strip()

        foto_claustro = request.FILES.get('foto_perfil')
        reconocimiento_pdf = request.FILES.get('reconocimiento_pdf')

        enviar_a_moderacion = 'accion_enviar' in request.POST
        guardar_borrador = 'accion_borrador' in request.POST

        if nombre:
            autor.nombre = nombre
        autor.genero = genero
        autor.genero_otro = genero_otro
        autor.rol_facultad = cargos_seleccionados[0] if cargos_seleccionados else 'OTRO'
        autor.orcid = orcid

        # Actualización de semblanzas (borrador o envío)
        autor.biografia_borrador = biografia
        autor.biografia_extendida_borrador = biografia_extendida

        if foto_claustro:
            autor.foto_perfil_borrador = foto_claustro
            autor.foto_perfil = foto_claustro
        if reconocimiento_pdf:
            autor.reconocimiento_pdf_borrador = reconocimiento_pdf

        if guardar_borrador:
            messages.success(request, 'Tus cambios se han guardado como borrador privado.')
        elif enviar_a_moderacion:
            autor.estado_semblanza = 'pendiente'
            autor.perfil_completado = False
            autor.motivo_rechazo_semblanza = ''
            autor.moderado_por_semblanza = None
            registrar_auditoria(request.user, "Envío de Semblanza", f"Envió su semblanza a revisión: {autor.nombre}")
            messages.info(request, 'Tu semblanza actualizada ha sido enviada a moderación.')

        autor.save()

        if cargos_seleccionados:
            autor.nombramientos.all().delete()
            for rol_codigo in cargos_seleccionados:
                Nombramiento.objects.create(autor=autor, rol=rol_codigo)

        autor.enlaces_profesionales.all().delete()
        plataformas = request.POST.getlist('enlace_plataforma[]')
        urls = request.POST.getlist('enlace_url[]')
        emojis = request.POST.getlist('enlace_emoji[]')

        for plat, u, em in zip(plataformas, urls, emojis):
            if plat.strip() and u.strip():
                EnlaceProfesional.objects.create(
                    autor=autor,
                    plataforma=plat.strip(),
                    url=u.strip(),
                    emoji=em.strip() if em.strip() else '🔗'
                )

    return redirect('mi_panel')


@login_required
def cambiar_password_propia_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            return JsonResponse({'success': True, 'message': 'Tu contraseña ha sido actualizada exitosamente.'})
        else:
            traducciones = {
                "This password is too short. It must contain at least 8 characters.": "La contraseña es muy corta. Debe contener al menos 8 caracteres.",
                "This password is too common.": "Esta contraseña es demasiado común o fácil de adivinar.",
                "This password is entirely numeric.": "La contraseña no puede ser completamente numérica.",
                "Your old password was entered incorrectly. Please enter it again.": "La contraseña actual es incorrecta. Por favor, ingrésala de nuevo.",
                "The two password fields didn't match.": "Las dos contraseñas nuevas no coinciden."
            }

            errores_lista = []
            for field, errors in form.errors.items():
                for error in errors:
                    error_es = traducciones.get(error, error)
                    errores_lista.append(error_es)

            return JsonResponse({'success': False, 'errors': errores_lista}, status=400)

    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)


@user_passes_test(es_superusuario, login_url='/login/')
def aprobar_semblanza_view(request, autor_id):
    autor = get_object_or_404(Autor, id=autor_id)

    if autor.biografia_borrador:
        autor.biografia = autor.biografia_borrador
    if autor.biografia_extendida_borrador:
        autor.biografia_extendida = autor.biografia_extendida_borrador
    if autor.foto_perfil_borrador:
        autor.foto_perfil = autor.foto_perfil_borrador
    if autor.reconocimiento_pdf_borrador:
        autor.reconocimiento_pdf = autor.reconocimiento_pdf_borrador

    autor.estado_semblanza = 'aprobado'
    autor.perfil_completado = True
    autor.motivo_rechazo_semblanza = ''
    autor.moderado_por_semblanza = request.user
    autor.save()

    registrar_auditoria(request.user, "Aprobación de Semblanza", f"Aprobó y publicó la semblanza de: {autor.nombre}")
    messages.success(request, f'La semblanza de "{autor.nombre}" ha sido aprobada y publicada oficialmente.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def rechazar_semblanza_view(request, autor_id):
    if request.method == 'POST':
        autor = get_object_or_404(Autor, id=autor_id)
        checks = request.POST.getlist('motivo_checks')
        texto_libre = request.POST.get('motivo_rechazo', '').strip()

        motivo_final = ""
        if checks:
            motivo_final += "Elementos a corregir:\n- " + "\n- ".join(checks)
        if texto_libre:
            motivo_final += f"\n\nObservaciones adicionales: {texto_libre}"

        autor.estado_semblanza = 'rechazado'
        autor.motivo_rechazo_semblanza = motivo_final
        autor.moderado_por_semblanza = request.user
        autor.save()
        registrar_auditoria(request.user, "Rechazo de Semblanza", f"Rechazó la semblanza de: {autor.nombre}")
        messages.warning(request, f'La semblanza de "{autor.nombre}" fue devuelta con observaciones.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def restablecer_semblanza_admin_view(request, autor_id):
    if request.method == 'POST':
        autor = get_object_or_404(Autor, id=autor_id)
        motivo = request.POST.get('motivo_restablecimiento', '').strip()

        autor.biografia = ''
        autor.biografia_borrador = ''
        autor.biografia_extendida = ''
        autor.biografia_extendida_borrador = ''
        autor.foto_perfil = None
        autor.foto_perfil_borrador = None
        autor.reconocimiento_pdf = None
        autor.reconocimiento_pdf_borrador = None
        autor.enlaces_profesionales.all().delete()
        autor.nombramientos.all().delete()

        autor.estado_semblanza = 'borrador'
        autor.perfil_completado = False

        mensaje_notif = "Un administrador ha restablecido tu ficha académica dejándola en blanco para su actualización."
        if motivo:
            mensaje_notif += f" Motivo: {motivo}"
        autor.motivo_rechazo_semblanza = mensaje_notif
        autor.moderado_por_semblanza = request.user
        autor.save()

        registrar_auditoria(request.user, "Restablecimiento de Semblanza", f"Restableció la ficha de: {autor.nombre}")
        messages.success(request, f'La semblanza de "{autor.nombre}" ha sido restablecida y vaciada exitosamente.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def editar_semblanza_admin_view(request, autor_id):
    autor = get_object_or_404(Autor, id=autor_id)
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        genero = request.POST.get('genero', 'NE')
        cargos_seleccionados = request.POST.getlist('roles_facultad')

        # Obtenemos los campos de texto del formulario modal
        biografia = request.POST.get('biografia_borrador', '').strip()
        biografia_extendida = request.POST.get('biografia_extendida_borrador', '').strip()

        if nombre:
            autor.nombre = nombre
        autor.genero = genero

        # Guardamos el texto en los campos oficiales Y en los borradores
        autor.biografia = biografia
        autor.biografia_borrador = biografia
        autor.biografia_extendida = biografia_extendida
        autor.biografia_extendida_borrador = biografia_extendida

        # Aprobamos la semblanza automáticamente al editar
        autor.estado_semblanza = 'aprobado'
        autor.perfil_completado = True
        autor.motivo_rechazo_semblanza = ''

        autor.save()

        if cargos_seleccionados:
            autor.nombramientos.all().delete()
            for rol_codigo in cargos_seleccionados:
                Nombramiento.objects.create(autor=autor, rol=rol_codigo)

        autor.enlaces_profesionales.all().delete()
        plataformas = request.POST.getlist('enlace_plataforma[]')
        urls = request.POST.getlist('enlace_url[]')
        emojis = request.POST.getlist('enlace_emoji[]')

        for plat, u, em in zip(plataformas, urls, emojis):
            if plat.strip() and u.strip():
                EnlaceProfesional.objects.create(
                    autor=autor,
                    plataforma=plat.strip(),
                    url=u.strip(),
                    emoji=em.strip() if em.strip() else '🔗'
                )

        registrar_auditoria(request.user, "Edición de Ficha Académica",
                            f"Editó y aprobó la semblanza de: {autor.nombre}")
        messages.success(request, f'Ficha académica de "{autor.nombre}" actualizada y aprobada exitosamente.')

    return redirect('panel_usuarios')


# ==============================================================================
# DIRECTORIO PÚBLICO DEL CLAUSTRO Y RED DE UNIVERSIDADES
# ==============================================================================

def directorio_profesores_view(request):
    # SOLUCIÓN BUG 2: Se eliminaron las exclusiones de biografía vacía para que
    # todos los autores aprobados se muestren, incluso sin semblanza corta.
    profesores_uabc_qs = Autor.objects.filter(
        es_profesor=True,
        estado_semblanza='aprobado',
        perfil_completado=True,
        institucion_origen__iexact='UABC'
    ).prefetch_related(
        'documentos', 'nombramientos', 'enlaces_profesionales', 'mensajes_recibidos'
    ).order_by('nombre')

    profesores_externos_qs = Autor.objects.filter(
        es_profesor=True,
        estado_semblanza='aprobado',
        perfil_completado=True
    ).exclude(
        institucion_origen__iexact='UABC'
    ).prefetch_related(
        'documentos', 'nombramientos', 'enlaces_profesionales', 'mensajes_recibidos'
    ).order_by('nombre')

    # Priorización: Los profesores que cumplen años hoy aparecen al inicio
    profesores_uabc = sorted(list(profesores_uabc_qs), key=lambda p: (not p.es_cumpleanos_hoy, p.nombre))
    profesores_externos = sorted(list(profesores_externos_qs), key=lambda p: (not p.es_cumpleanos_hoy, p.nombre))

    # Identificar a quiénes ya felicitó el usuario autenticado el día de hoy
    ids_felicitados_hoy = set()
    if request.user.is_authenticated:
        hoy = timezone.localdate()
        ids_felicitados_hoy = set(
            MensajeCumpleanos.objects.filter(
                de_usuario=request.user,
                fecha_envio__date=hoy
            ).values_list('para_docente_id', flat=True)
        )

    context = {
        'profesores_uabc': profesores_uabc,
        'profesores_externos': profesores_externos,
        'hoy': timezone.localdate(),
        'ids_felicitados_hoy': ids_felicitados_hoy,
    }
    return render(request, 'profesores_directorio.html', context)


def universidades_colaboradoras_view(request):
    instituciones = Autor.objects.filter(
        documentos__estado='aprobado'
    ).exclude(
        institucion_origen__isnull=True
    ).exclude(
        institucion_origen__exact=''
    ).exclude(
        institucion_origen__iexact='UABC'
    ).values('institucion_origen').distinct()

    red_colaboracion = []
    total_investigadores_global = 0
    total_obras_ids = set()

    for inst in instituciones:
        nombre_inst = inst['institucion_origen']
        autores_inst = Autor.objects.filter(
            institucion_origen__iexact=nombre_inst,
            documentos__estado='aprobado'
        ).distinct()

        obras = Articulo.objects.filter(
            filtro_publico_articulos(),
            autor__in=autores_inst
        ).distinct().order_by('-created_at')

        total_investigadores_global += autores_inst.count()
        for o in obras:
            total_obras_ids.add(o.id)

        # Extraer siglas del formato "Nombre Universidad (SIGLAS)"
        siglas = ""
        match = re.search(r'\(([^()]+)\)$', nombre_inst)
        if match:
            siglas = match.group(1).upper()
        else:
            palabras = [p for p in nombre_inst.split() if p.isalpha() and len(p) > 2]
            siglas = "".join([p[0].upper() for p in palabras])[:5]

        red_colaboracion.append({
            'nombre': nombre_inst,
            'siglas': siglas or 'UNI',
            'total_investigadores': autores_inst.count(),
            'investigadores': autores_inst,
            'total_obras': obras.count(),
            'ultimas_obras': obras[:3]
        })

    context = {
        'red_colaboracion': red_colaboracion,
        'total_instituciones': len(red_colaboracion),
        'total_investigadores_global': total_investigadores_global,
        'total_obras_global': len(total_obras_ids),
    }
    return render(request, 'universidades_red.html', context)


@user_passes_test(es_superusuario, login_url='/login/')
def panel_usuarios_view(request):
    fecha_filtro = request.GET.get('fecha', '').strip()
    registros = RegistroAuditoria.objects.all()

    if fecha_filtro:
        try:
            f_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
            registros = registros.filter(created_at__date=f_obj)
        except ValueError:
            pass

    # <--- MEJORA 2: Paginación en Paneles --->
    todos_documentos_qs = Articulo.objects.all().order_by('-created_at')
    paginator_docs = Paginator(todos_documentos_qs, 15)
    page_docs = request.GET.get('page_docs')
    todos_documentos = paginator_docs.get_page(page_docs)

    documentos_pendientes_qs = Articulo.objects.filter(estado='pendiente').order_by('-created_at')
    paginator_pendientes = Paginator(documentos_pendientes_qs, 15)
    page_pendientes = request.GET.get('page_pendientes')
    documentos_pendientes = paginator_pendientes.get_page(page_pendientes)

    todas_semblanzas_qs = Autor.objects.filter(es_profesor=True).exclude(estado_semblanza='borrador').order_by('nombre')
    paginator_semb = Paginator(todas_semblanzas_qs, 15)
    page_semb = request.GET.get('page_semb')
    todas_semblanzas = paginator_semb.get_page(page_semb)

    context = {
        'pendientes': User.objects.filter(is_active=False, is_staff=True),
        'administrativos': User.objects.filter(is_superuser=False, is_staff=True, is_active=True),
        'superusuarios': User.objects.filter(is_superuser=True, is_active=True),
        'todos_documentos': todos_documentos,
        'documentos_pendientes': documentos_pendientes,
        'semblanzas_pendientes': Autor.objects.filter(estado_semblanza='pendiente'),
        'todas_semblanzas': todas_semblanzas,
        'es_principal': es_superusuario_principal(request.user),
        'registros': registros.order_by('-created_at'),
        'fecha_seleccionada': fecha_filtro,
    }
    return render(request, 'panel_usuarios.html', context)


@login_required
def enviar_felicitacion_cumpleanos_view(request, autor_id):
    if request.method == 'POST':
        destinatario_autor = get_object_or_404(Autor, id=autor_id)
        mensaje_texto = request.POST.get('mensaje', '').strip()

        # Validar que no se autofelicite
        if hasattr(request.user, 'autor') and request.user.autor == destinatario_autor:
            messages.error(request, 'No puedes enviarte una felicitación a ti mismo.')
            return redirect('directorio_profesores')

        # Validar que hoy sea el cumpleaños del colega
        if not destinatario_autor.es_cumpleanos_hoy:
            messages.error(request, 'Solo puedes enviar felicitaciones el día del cumpleaños del docente.')
            return redirect('directorio_profesores')

        # Validar que el remitente sea un colega docente o superusuario
        es_colega_docente = hasattr(request.user, 'autor') and request.user.autor.es_profesor
        if not es_colega_docente and not request.user.is_superuser:
            messages.error(request, 'Solo los colegas docentes pueden enviar felicitaciones de cumpleaños.')
            return redirect('directorio_profesores')

        # Validar que no haya enviado una felicitación el día de hoy
        hoy = timezone.localdate()
        ya_felicito = MensajeCumpleanos.objects.filter(
            para_docente=destinatario_autor,
            de_usuario=request.user,
            fecha_envio__date=hoy
        ).exists()

        if ya_felicito:
            messages.warning(request, f'Ya has felicitado a {destinatario_autor.nombre} el día de hoy.')
            return redirect('directorio_profesores')

        if mensaje_texto:
            MensajeCumpleanos.objects.create(
                para_docente=destinatario_autor,
                de_usuario=request.user,
                mensaje=mensaje_texto
            )
            messages.success(request, f'Tu felicitación para {destinatario_autor.nombre} ha sido enviada con éxito.')
        else:
            messages.error(request, 'No se pudo enviar un mensaje vacío.')
    return redirect('directorio_profesores')


@user_passes_test(es_superusuario, login_url='/login/')
def aprobar_documento_view(request, doc_id):
    articulo = get_object_or_404(Articulo, id=doc_id)
    articulo.estado = 'aprobado'
    articulo.motivo_rechazo = ''
    articulo.moderado_por = request.user
    articulo.save()

    registrar_auditoria(request.user, "Aprobación de Documento", f"Aprobó la obra: {articulo.titulo}")
    messages.success(request, f'La obra "{articulo.titulo}" ha sido aprobada y publicada exitosamente.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def rechazar_documento_view(request, doc_id):
    if request.method == 'POST':
        articulo = get_object_or_404(Articulo, id=doc_id)
        checks = request.POST.getlist('motivo_checks')
        texto_libre = request.POST.get('motivo_rechazo', '').strip()

        motivo_final = f"Elementos a corregir:\n- " + "\n- ".join(checks) if checks else ""
        if texto_libre:
            motivo_final += f"\n\nObservaciones adicionales: {texto_libre}"

        articulo.estado = 'rechazado'
        articulo.motivo_rechazo = motivo_final
        articulo.moderado_por = request.user
        articulo.save()

        registrar_auditoria(request.user, "Rechazo de Documento", f"Rechazó la obra: {articulo.titulo}")
        messages.warning(request,
                         f'La obra "{articulo.titulo}" ha sido devuelta al autor con observaciones de corrección.')
    return redirect('panel_usuarios')


@login_required
def eliminar_documento_view(request, doc_id):
    articulo = get_object_or_404(Articulo, id=doc_id)

    if not (request.user.is_superuser or articulo.subido_por == request.user):
        messages.error(request, "No tienes autorización para eliminar esta obra.")
        return redirect('mi_panel')

    titulo_doc = articulo.titulo
    articulo.delete()

    registrar_auditoria(request.user, "Eliminación de Documento", f"Eliminó la obra: {titulo_doc}")
    messages.success(request, f'La obra "{titulo_doc}" ha sido eliminada exitosamente del sistema.')

    # Lógica de redirección inteligente corregida
    referer = request.META.get('HTTP_REFERER', '')

    # Comprobamos si la petición vino del panel de administración (cuya URL es /gestion-usuarios/)
    if 'gestion-usuarios' in referer:
        return redirect('panel_usuarios')

    # Si vino de cualquier otro lado (como 'mi_panel'), lo devolvemos ahí
    return redirect('mi_panel')


@user_passes_test(es_superusuario, login_url='/login/')
def aprobar_usuario_view(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    usuario.is_active = True
    usuario.save()
    registrar_auditoria(request.user, "Aprobación de Solicitud de Usuario", f"Aprobó la cuenta de: {usuario.username}")
    messages.success(request, f'La cuenta de "{usuario.username}" ha sido aprobada y activada exitosamente.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def rechazar_usuario_view(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    nombre_usr = usuario.username
    if hasattr(usuario, 'autor'):
        usuario.autor.delete()
    usuario.delete()
    registrar_auditoria(request.user, "Rechazo de Solicitud de Usuario", f"Rechazó la solicitud de: {nombre_usr}")
    messages.warning(request, f'La solicitud de registro de "{nombre_usr}" ha sido rechazada y eliminada.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def toggle_estado_usuario_view(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    if usuario == request.user or (usuario.id == 1 or usuario.username.lower() == 'yaele'):
        messages.error(request, 'No puedes suspender a este usuario protegido.')
        return redirect('panel_usuarios')

    if not es_superusuario_principal(request.user):
        admin_pass = request.POST.get('admin_password', '').strip()
        if not request.user.check_password(admin_pass):
            messages.error(request, 'Contraseña de administrador incorrecta. No se pudo cambiar el estado.')
            return redirect('panel_usuarios')

    usuario.is_active = not usuario.is_active
    usuario.save()
    estado_txt = "activada" if usuario.is_active else "suspendida"
    registrar_auditoria(request.user, f"Cambio de Estado de Cuenta ({estado_txt})",
                        f"Modificó el acceso de: {usuario.username}")
    messages.success(request,
                     f'La cuenta de "{usuario.username}" ha sido {estado_txt} por el administrador {request.user.username}.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def toggle_superuser_view(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    if usuario.id == 1 or usuario.username.lower() == 'yaele':
        messages.error(request, 'No se pueden modificar los permisos del superusuario principal.')
        return redirect('panel_usuarios')

    usuario.is_superuser = not usuario.is_superuser
    usuario.is_staff = True
    usuario.save()

    estado_super = "otorgó privilegios de Superusuario" if usuario.is_superuser else "retiró privilegios de Superusuario"
    registrar_auditoria(request.user, "Cambio de Privilegios Superusuario", f"{estado_super} a: {usuario.username}")
    messages.success(request, f'Se han actualizado los privilegios de superusuario para "{usuario.username}".')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def eliminar_usuario_view(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    if usuario == request.user or usuario.id == 1 or usuario.username.lower() == 'yaele':
        messages.error(request, 'No puedes eliminar esta cuenta protegida.')
        return redirect('panel_usuarios')

    if not es_superusuario_principal(request.user):
        admin_pass = request.POST.get('admin_password', '').strip()
        if not request.user.check_password(admin_pass):
            messages.error(request, 'Contraseña de administrador incorrecta. No se pudo eliminar la cuenta.')
            return redirect('panel_usuarios')

    nombre_usr = usuario.username
    if hasattr(usuario, 'autor'):
        usuario.autor.delete()
    usuario.delete()
    registrar_auditoria(request.user, "Eliminación de Cuenta", f"Eliminó permanentemente al usuario: {nombre_usr}")
    messages.error(request,
                   f'La cuenta de "{nombre_usr}" ha sido eliminada permanentemente por el administrador {request.user.username}.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def cambiar_rol_usuario_view(request, user_id):
    if request.method == 'POST':
        usuario = get_object_or_404(User, id=user_id)

        if usuario.id == 1 or usuario.username.lower() == 'yaele':
            messages.error(request, 'No se pueden modificar los permisos del superusuario principal.')
            return redirect('panel_usuarios')

        if not es_superusuario_principal(request.user):
            admin_pass = request.POST.get('admin_password', '').strip()
            if not request.user.check_password(admin_pass):
                messages.error(request, 'Contraseña de administrador incorrecta. No se pudo cambiar el rol.')
                return redirect('panel_usuarios')

        nuevo_rol = request.POST.get('nuevo_rol')
        institucion_externa = request.POST.get('institucion', '').strip()

        autor, creado = Autor.objects.get_or_create(
            usuario=usuario,
            defaults={'nombre': usuario.get_full_name() or usuario.username, 'correo': usuario.email}
        )

        if nuevo_rol == 'superuser':
            usuario.is_superuser = True
            usuario.is_staff = True
            autor.es_profesor = False
            autor.es_externo = False
        elif nuevo_rol == 'administrativo':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = False
            autor.es_externo = False
        elif nuevo_rol == 'docente':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = True
            autor.es_externo = False
            autor.institucion_origen = 'UABC'
        elif nuevo_rol == 'externo':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = True
            autor.es_externo = True
            if institucion_externa:
                autor.institucion_origen = institucion_externa

        autor.save()
        usuario.save()

        registrar_auditoria(request.user, "Cambio de Rol de Usuario",
                            f"Actualizó el rol de {usuario.username} a: {nuevo_rol}")
        messages.success(request,
                         f'El rol de "{usuario.username}" ha sido actualizado a "{nuevo_rol}" por el administrador {request.user.username}.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def editar_ficha_usuario_admin_view(request, user_id):
    if request.method == 'POST':
        usuario = get_object_or_404(User, id=user_id)

        if (usuario.id == 1 or usuario.username.lower() == 'yaele') and not es_superusuario_principal(request.user):
            messages.error(request, 'No tienes permisos para modificar al superusuario principal.')
            return redirect('panel_usuarios')

        if not es_superusuario_principal(request.user):
            admin_pass = request.POST.get('admin_password', '').strip()
            if not request.user.check_password(admin_pass):
                messages.error(request, 'Contraseña de administrador incorrecta. No se pudieron guardar los cambios.')
                return redirect('panel_usuarios')

        nuevo_username = request.POST.get('username', '').strip()
        nuevo_email = request.POST.get('email', '').strip()
        nuevo_nombre = request.POST.get('nombre_completo', '').strip()
        nueva_fnac = request.POST.get('fecha_nacimiento', '').strip()
        nuevo_numemp = request.POST.get('numero_empleado', '').strip()

        if nuevo_username and nuevo_username != usuario.username:
            if User.objects.filter(username=nuevo_username).exists():
                messages.error(request, f'El nombre de usuario "{nuevo_username}" ya está en uso.')
                return redirect('panel_usuarios')
            usuario.username = nuevo_username

        if nuevo_email != usuario.email:
            if nuevo_email and User.objects.filter(email=nuevo_email).exists():
                messages.error(request, f'El correo electrónico "{nuevo_email}" ya está registrado.')
                return redirect('panel_usuarios')
            usuario.email = nuevo_email

        usuario.save()

        # SOLUCIÓN BUG 1: Se eliminó el "if not usuario.is_superuser:" para permitir
        # que el sistema también actualice los perfiles (Autor) de los administradores.
        autor, creado = Autor.objects.get_or_create(
            usuario=usuario,
            defaults={
                'nombre': nuevo_nombre or usuario.username,
                'correo': usuario.email,
                'es_profesor': False
            }
        )

        if nuevo_nombre:
            autor.nombre = nuevo_nombre
        if nuevo_email:
            autor.correo = nuevo_email

        if hasattr(autor, 'numero_empleado'):
            autor.numero_empleado = nuevo_numemp if nuevo_numemp else None

        if nueva_fnac:
            try:
                autor.fecha_nacimiento = datetime.strptime(nueva_fnac, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            autor.fecha_nacimiento = None

        autor.save()

        registrar_auditoria(request.user, "Edición de Ficha de Usuario",
                            f"Modificó los datos de la cuenta: {usuario.username}")
        messages.success(request, f'La ficha y datos de "{usuario.username}" han sido actualizados exitosamente.')
    return redirect('panel_usuarios')


@login_required
def crear_autor_rapido_view(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        institucion = request.POST.get('institucion', 'UABC').strip()
        es_externo = request.POST.get('es_externo', 'false') == 'true'
        universidad_nombre = request.POST.get('universidad', '').strip()
        siglas = request.POST.get('siglas', '').strip()

        if not nombre:
            return JsonResponse({'success': False, 'error': 'El nombre es obligatorio.'}, status=400)

        if es_externo and universidad_nombre and siglas:
            Universidad.objects.get_or_create(
                nombre__iexact=universidad_nombre,
                defaults={
                    'nombre': universidad_nombre,
                    'siglas': siglas.upper()
                }
            )
            institucion = f"{universidad_nombre} ({siglas.upper()})"

        nuevo_autor = Autor.objects.create(
            nombre=nombre,
            institucion_origen=institucion,
            es_profesor=True,
            es_externo=es_externo
        )
        return JsonResponse({
            'success': True,
            'id': nuevo_autor.id,
            'nombre': nuevo_autor.nombre,
            'institucion': nuevo_autor.institucion_origen
        })
    return JsonResponse({'success': False}, status=405)


@user_passes_test(es_superusuario, login_url='/login/')
def ver_subidas_usuario_view(request, user_id):
    usuario_consultado = get_object_or_404(User, id=user_id)

    if usuario_consultado.email and not hasattr(usuario_consultado, 'autor'):
        autor_huerfano = Autor.objects.filter(correo__iexact=usuario_consultado.email, usuario__isnull=True).first()
        if autor_huerfano:
            autor_huerfano.usuario = usuario_consultado
            autor_huerfano.save()

    correo_usr = usuario_consultado.email
    nombre_autor = usuario_consultado.autor.nombre if hasattr(usuario_consultado,
                                                              'autor') else usuario_consultado.username

    cargados_por_cuenta = Articulo.objects.filter(subido_por=usuario_consultado).order_by('-created_at')

    for obra in cargados_por_cuenta:
        if not obra.subido_por:
            obra.subido_por = usuario_consultado
            obra.save()

    asociados_como_autor = Articulo.objects.filter(
        Q(autor__usuario=usuario_consultado) |
        Q(autor__correo__iexact=correo_usr) |
        Q(autor__nombre__iexact=nombre_autor)
    ).distinct().order_by('-created_at')

    context = {
        'usuario_consultado': usuario_consultado,
        'cargados_por_cuenta': cargados_por_cuenta,
        'asociados_como_autor': asociados_como_autor,
        'total_cargados': cargados_por_cuenta.count(),
        'total_autor': asociados_como_autor.count(),
    }
    return render(request, 'usuario_documentos.html', context)


@user_passes_test(es_superusuario, login_url='/login/')
def restablecer_password_usuario_view(request, user_id):
    if request.method == 'POST':
        usuario = get_object_or_404(User, id=user_id)
        nueva_pass = request.POST.get('nueva_password', '').strip()

        if not es_superusuario_principal(request.user):
            admin_pass = request.POST.get('admin_password', '').strip()
            if not request.user.check_password(admin_pass):
                messages.error(request, 'Tu contraseña de administrador es incorrecta. No se pudo cambiar la clave.')
                return redirect('panel_usuarios')

        if nueva_pass:
            usuario.set_password(nueva_pass)
            usuario.save()
            registrar_auditoria(request.user, "Restablecimiento de Contraseña",
                                f"Asignó nueva clave al usuario: {usuario.username}")
            messages.success(request, f'La contraseña del usuario "{usuario.username}" ha sido restablecida.')
        else:
            messages.error(request, 'La nueva contraseña no puede estar vacía.')
    return redirect('panel_usuarios')