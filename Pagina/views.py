import logging
import re
import unicodedata
import json

logger = logging.getLogger(__name__)
from difflib import SequenceMatcher
from collections import defaultdict
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
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.core.paginator import Paginator  # <--- Agregado para Paginación
from django.core import serializers
from django.db import transaction

from .models import (
    Articulo, Entidad, Area, TipoContenido, Autor, MensajeCumpleanos,
    Nombramiento, EnlaceProfesional, RegistroAuditoria, Universidad,
    InvitacionCoautoria, MensajeInterno, ROL_DOCENTE_OPCIONES, HistorialFusion
)
import random
from .forms import ArticuloForm
from .emails import (
    notificar_solicitud_registro_usuario,
    notificar_solicitud_registro_admins,
    notificar_solicitud_tutor_auxiliar,
    notificar_visto_bueno_auxiliar,
    notificar_aprobacion_cuenta,
    notificar_ascenso_superadmin,
    notificar_codigo_verificacion_registro,
    notificar_codigo_recuperacion_password,
    notificar_alerta_cambio_password,
    notificar_obra_aprobada,
    notificar_obra_rechazada,
    notificar_invitacion_coautoria,
    notificar_respuesta_coautoria,
    notificar_nuevo_mensaje_interno,
)


def es_superusuario(user):
    return user.is_authenticated and user.is_superuser


def es_superusuario_principal(user):
    if not user or not user.is_authenticated or not user.is_superuser:
        return False
    if user.username.lower() == 'yaele' or user.id == 1:
        return True
    try:
        primer_super = User.objects.filter(is_superuser=True).order_by('id').first()
        if primer_super and user.id == primer_super.id:
            return True
    except Exception:
        pass
    return False


def filtro_publico_articulos():
    return Q(estado='aprobado', en_papelera=False)


def registrar_auditoria(usuario, accion, detalle=""):
    """Registra una acción administrativa en el buzón de auditoría."""
    RegistroAuditoria.objects.create(
        admin_usuario=usuario if usuario and usuario.is_authenticated else None,
        accion=accion,
        detalle=detalle
    )


def limpiar_autores_huerfanos(minutos_gracia=15, excluir_ids=None):
    """
    Elimina autores auxiliares que:
    1. No tienen cuenta de usuario vinculada (usuario__isnull=True).
    2. No tienen documentos/artículos asociados (documentos__isnull=True).
    3. No tienen tesis asesoradas (tesis_asesoradas__isnull=True).
    4. No tienen invitaciones de coautoría recibidas (invitaciones_recibidas__isnull=True).
    5. Opcional: Tienen más de `minutos_gracia` de haber sido creados (para no borrar a alguien en medio de llenar el formulario), o forzar purga si minutos_gracia=0.
    """
    qs = Autor.objects.filter(
        usuario__isnull=True,
        documentos__isnull=True,
        tesis_asesoradas__isnull=True,
        tesis_coasesoradas__isnull=True,
        invitaciones_recibidas__isnull=True
    )
    if excluir_ids:
        qs = qs.exclude(id__in=excluir_ids)
    if minutos_gracia and minutos_gracia > 0:
        limite = timezone.now() - timedelta(minutes=minutos_gracia)
        qs = qs.filter(Q(created_at__lte=limite) | Q(created_at__isnull=True))

    total, _ = qs.delete()
    return total


def obtener_autores_activos_catalogo():
    # Purgar huérfanos que lleven más de 15 minutos abandonados
    try:
        limpiar_autores_huerfanos(minutos_gracia=15)
    except Exception:
        pass

    return Autor.objects.filter(
        es_profesor=True
    ).exclude(
        usuario__is_superuser=True
    ).distinct().order_by('nombre')


TITULOS_HONORIFICOS = {
    'dr', 'dra', 'doctor', 'doctora', 'lic', 'licenciado', 'licenciada',
    'mtro', 'mtra', 'maestro', 'maestra', 'ing', 'ingeniero', 'ingeniera',
    'prof', 'profa', 'profesor', 'profesora', 'docente', 'msc', 'phd'
}


def normalizar_nombre_autor(nombre):
    """Limpia tildes, signos de puntuación y títulos honoríficos para comparación fonética/textual."""
    if not nombre:
        return ''
    s = unicodedata.normalize('NFKD', str(nombre)).encode('ASCII', 'ignore').decode('utf-8').lower()
    s = re.sub(r'[^a-z0-9\s]', ' ', s)
    tokens = [t for t in s.split() if t not in TITULOS_HONORIFICOS]
    return ' '.join(tokens)


def detectar_grupos_autores_parecidos(autores_queryset):
    """
    Analiza todos los autores registrados y detecta clusters de autores con nombres similares,
    variantes tipográficas, omisión de títulos académicos o nombres parciales.
    """
    autores = list(autores_queryset)
    if len(autores) < 2:
        return []

    info = []
    for a in autores:
        norm = normalizar_nombre_autor(a.nombre)
        tokens = set(norm.split())
        info.append({'autor': a, 'norm': norm, 'tokens': tokens})

    adj = defaultdict(dict)
    for i in range(len(info)):
        for j in range(i + 1, len(info)):
            a1, a2 = info[i], info[j]
            norm1, norm2 = a1['norm'], a2['norm']
            if not norm1 or not norm2:
                continue

            similitud = 0
            motivo = ''

            if norm1 == norm2:
                similitud = 100
                motivo = 'Nombre idéntico (variación de títulos honoríficos Dr./Lic.)'
            else:
                ratio = SequenceMatcher(None, norm1, norm2).ratio()
                if ratio >= 0.82:
                    similitud = int(ratio * 100)
                    motivo = f'Coincidencia tipográfica / fonética ({similitud}%)'
                elif a1['tokens'] and a2['tokens']:
                    inter = a1['tokens'].intersection(a2['tokens'])
                    if inter == a1['tokens'] or inter == a2['tokens']:
                        longest_token = max(len(t) for t in inter) if inter else 0
                        if len(inter) >= 2 or longest_token >= 5:
                            similitud = int((len(inter) / max(len(a1['tokens']), len(a2['tokens']))) * 100)
                            motivo = f'Nombre parcial / subconjunto ({similitud}%)'

            if similitud >= 50:
                adj[a1['autor'].id][a2['autor'].id] = (similitud, motivo)
                adj[a2['autor'].id][a1['autor'].id] = (similitud, motivo)

    visited = set()
    grupos = []
    autores_map = {a.id: a for a in autores}

    for aid in autores_map:
        if aid not in visited and aid in adj:
            component = []
            queue = [aid]
            visited.add(aid)
            while queue:
                curr = queue.pop(0)
                component.append(curr)
                for neighbor in adj[curr]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)

            if len(component) > 1:
                miembros = [autores_map[mid] for mid in component]

                def puntuar_autor_canonico(a):
                    score = 0
                    if a.usuario:
                        score += 1000
                    docs_cnt = getattr(a, 'num_documentos', None)
                    if docs_cnt is None:
                        try:
                            docs_cnt = a.documentos.count()
                        except Exception:
                            docs_cnt = 0
                    asesorias_cnt = getattr(a, 'num_asesorias', None)
                    if asesorias_cnt is None:
                        try:
                            asesorias_cnt = a.tesis_asesoradas.count() + a.tesis_coasesoradas.count()
                        except Exception:
                            asesorias_cnt = 0

                    score += (docs_cnt * 100) + (asesorias_cnt * 50)
                    if a.codigo_institucional and str(a.codigo_institucional).startswith('FCA-'):
                        score += 80
                    if a.orcid:
                        score += 20
                    score += len(a.nombre)
                    return score

                miembros.sort(key=puntuar_autor_canonico, reverse=True)
                principal = miembros[0]

                duplicados = []
                for m in miembros[1:]:
                    sim, mot = adj[m.id].get(principal.id, (75, 'Variante detectada en este grupo'))
                    duplicados.append({
                        'autor': m,
                        'similitud': sim,
                        'motivo': mot,
                    })

                todos_miembros = []
                for m in miembros:
                    is_princ = (m.id == principal.id)
                    sim, mot = (100, 'Canónico sugerido (mayor actividad o antigüedad)') if is_princ else adj[m.id].get(principal.id, (75, 'Variante detectada'))
                    todos_miembros.append({
                        'autor': m,
                        'es_sugerido': is_princ,
                        'similitud': sim,
                        'motivo': mot,
                    })

                duplicados_ids = [m.id for m in miembros[1:]]

                grupos.append({
                    'id_grupo': f'grupo_{principal.id}',
                    'nombre_representativo': principal.nombre,
                    'principal': principal,
                    'total_variantes': len(miembros),
                    'duplicados': duplicados,
                    'duplicados_ids_json': json.dumps(duplicados_ids),
                    'todos_miembros': todos_miembros,
                })

    grupos.sort(key=lambda g: (-g['total_variantes'], g['nombre_representativo']))
    return grupos



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
    # Se excluyen las entradas internas del sistema (FCA UABC, tutores, cómputo, soporte)
    # que no son instituciones reales para colaboradores externos o independientes.
    return Universidad.objects.exclude(
        nombre__istartswith='FCA '
    ).order_by('nombre')


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
        context['investigadores_claustro'] = Autor.objects.filter(usuario__isnull=False, es_profesor=True).count()
        context['universidades_aliadas'] = Universidad.objects.count()

        # <--- TENDENCIAS DINÁMICAS (Temas con obras reales en el catálogo) --->
        from collections import Counter
        kw_counter = Counter()
        for art in articulos_visibles:
            if art.palabras_clave:
                for kw in art.palabras_clave.split(','):
                    limpio = kw.strip().replace('-', ' ').title()
                    if limpio and len(limpio) > 2 and limpio.lower() not in ['prueba', 'test']:
                        kw_counter[limpio] += 1

        tendencias = [k for k, _ in kw_counter.most_common(5)]
        if len(tendencias) < 5:
            tipos_top = TipoContenido.objects.filter(articulo__in=articulos_visibles).annotate(
                total=Count('articulo')
            ).order_by('-total')
            for t in tipos_top:
                nom = t.nombre.strip()
                if nom and nom not in tendencias:
                    tendencias.append(nom)
                if len(tendencias) >= 5:
                    break
        context['tendencias_top'] = tendencias[:5]

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

        mi_autor = getattr(self.request.user, 'autor', None)
        es_auxiliar = bool(mi_autor and mi_autor.es_auxiliar and mi_autor.profesor_tutor and mi_autor.aprobado_por_tutor)
        tutor = mi_autor.profesor_tutor if es_auxiliar else None

        es_confianza = False
        if mi_autor and mi_autor.is_trusted_publisher:
            es_confianza = True
        elif es_auxiliar and tutor and tutor.is_trusted_publisher:
            es_confianza = True

        if self.request.user.is_superuser:
            articulo.estado = 'aprobado'
        elif es_confianza:
            articulo.estado = 'aprobado'
            articulo.es_subida_automatica = True
        else:
            articulo.estado = 'pendiente'

        articulo.save()
        form.save_m2m()

        # Si fue subido por un auxiliar, asegurarse de que el profesor tutor esté vinculado como autor
        if es_auxiliar and tutor:
            if not articulo.autor.filter(id=tutor.id).exists():
                articulo.autor.add(tutor)

        # Limpiar autores huérfanos que se hayan creado en el proceso pero no se vincularon a ninguna obra
        try:
            limpiar_autores_huerfanos(minutos_gracia=0, excluir_ids=articulo.autor.values_list('id', flat=True))
        except Exception:
            pass

        # Generar invitación de coautoría para colegas que tienen cuenta registrada
        for aut in articulo.autor.all():
            if aut.usuario and aut.usuario != self.request.user and (not es_auxiliar or aut != tutor):
                inv, created = InvitacionCoautoria.objects.get_or_create(
                    articulo=articulo,
                    autor_invitado=aut,
                    defaults={
                        'invitado_por': self.request.user,
                        'estado': 'pendiente',
                        'mensaje': f"{self.request.user.get_full_name() or self.request.user.username} te ha acreditado como coautor en '{articulo.titulo}'."
                    }
                )
                if created:
                    try:
                        notificar_invitacion_coautoria(inv)
                    except Exception as e:
                        logger.warning(f"Error al enviar correo de invitación de coautoría: {e}")

        if es_auxiliar and tutor:
            try:
                MensajeInterno.objects.create(
                    remitente=self.request.user,
                    destinatario=tutor,
                    asunto=f"Obra cargada por tu Auxiliar: {articulo.titulo}",
                    cuerpo=f"Tu Auxiliar de Investigación FCA, {mi_autor.nombre} (Matrícula: {mi_autor.matricula_estudiante or 'S/N'}), ha cargado la obra '{articulo.titulo}' a tu catálogo institucional.",
                    es_soporte=False
                )
            except Exception:
                pass
            registrar_auditoria(self.request.user, "Subida de Obra por Auxiliar", f"Auxiliar {self.request.user.username} subió la obra '{articulo.titulo}' para su tutor {tutor.nombre}")
            messages.success(self.request, f'Obra "{articulo.titulo}" cargada exitosamente al catálogo del Dr. {tutor.nombre}.')
        elif es_confianza and not self.request.user.is_superuser:
            registrar_auditoria(self.request.user, "Publicación Automática (Trusted Publisher)", f"Obra aprobada automáticamente por credencial de confianza: {articulo.titulo}")
            messages.success(self.request, f'¡Tu obra "{articulo.titulo}" ha sido aprobada y publicada automáticamente gracias a tu credencial de Publicador de Confianza!')
        elif self.request.user.is_superuser:
            registrar_auditoria(self.request.user, "Subida de Obra (SuperAdmin)", f"Subió la obra: {articulo.titulo}")
            messages.success(self.request, f'Obra "{articulo.titulo}" publicada exitosamente.')
        elif mi_autor and (getattr(mi_autor, 'es_operador_tecnico', False) or mi_autor.rol_facultad == 'DEP_TEC'):
            registrar_auditoria(self.request.user, "Subida de Obra por Operador Técnico", f"Operador Técnico {self.request.user.username} cargó obra para digitalización: '{articulo.titulo}'")
            messages.info(self.request, f'Obra "{articulo.titulo}" digitalizada y cargada exitosamente. Ha sido enviada a la cola de revisión de la administración.')
        else:
            registrar_auditoria(self.request.user, "Subida de Obra", f"Subió la obra: {articulo.titulo}")
            messages.info(self.request, f'Tu obra "{articulo.titulo}" ha sido enviada y quedará en espera de revisión por la administración.')

        return redirect('mi_panel')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['autores'] = obtener_autores_activos_catalogo()
        context['tipos_contenido'] = TipoContenido.objects.all()
        context['areas'] = Area.objects.all()
        context['idiomas_existentes'] = obtener_idiomas_unicos()
        context['universidades'] = obtener_o_sincronizar_universidades()
        mi_autor = getattr(self.request.user, 'autor', None)
        if mi_autor and mi_autor.es_auxiliar and mi_autor.profesor_tutor and mi_autor.aprobado_por_tutor:
            context['es_auxiliar_delegado'] = True
            context['profesor_tutor'] = mi_autor.profesor_tutor
        if mi_autor and (getattr(mi_autor, 'es_operador_tecnico', False) or mi_autor.rol_facultad == 'DEP_TEC'):
            context['es_operador_tecnico'] = True
        return context


@method_decorator(login_required, name='dispatch')
class ArticuloDocenteEditarView(UpdateView):
    model = Articulo
    form_class = ArticuloForm
    template_name = 'Formulario.html'

    def dispatch(self, request, *args, **kwargs):
        articulo = self.get_object()
        es_dueno = (articulo.subido_por == request.user)
        es_auxiliar_autorizado = False
        if hasattr(request.user, 'autor') and request.user.autor and request.user.autor.es_auxiliar:
            tutor = request.user.autor.profesor_tutor
            if tutor and request.user.autor.aprobado_por_tutor:
                if (tutor.usuario and articulo.subido_por == tutor.usuario) or articulo.autor.filter(id=tutor.id).exists():
                    es_auxiliar_autorizado = True

        if not (request.user.is_superuser or es_dueno or es_auxiliar_autorizado):
            return HttpResponseForbidden("No tienes autorización para editar esta obra.")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        articulo = form.save(commit=False)
        if articulo.idioma:
            articulo.idioma = articulo.idioma.strip().title()

        mi_autor = getattr(self.request.user, 'autor', None)
        es_auxiliar = bool(mi_autor and mi_autor.es_auxiliar and mi_autor.profesor_tutor and mi_autor.aprobado_por_tutor)
        tutor = mi_autor.profesor_tutor if es_auxiliar else None

        es_confianza = False
        if mi_autor and mi_autor.is_trusted_publisher:
            es_confianza = True
        elif es_auxiliar and tutor and tutor.is_trusted_publisher:
            es_confianza = True

        if es_auxiliar and tutor:
            if articulo.estado in ['rechazado', 'pendiente'] and not self.request.user.is_superuser:
                if es_confianza:
                    articulo.estado = 'aprobado'
                    articulo.es_subida_automatica = True
                    articulo.chequeado_por_moderador = False
                    articulo.motivo_rechazo = ''
                    articulo.moderado_por = None
                    messages.success(self.request, f"Obra actualizada y publicada directamente gracias a la Credencial de Confianza del Dr. {tutor.nombre}.")
                    registrar_auditoria(self.request.user, "Edición de Obra por Auxiliar", f"Auxiliar {self.request.user.username} publicó directamente por confianza: {articulo.titulo}")
                else:
                    articulo.estado = 'pendiente'
                    articulo.motivo_rechazo = ''
                    articulo.moderado_por = None
                    messages.info(self.request, f"Has reenviado la obra corregida del Dr. {tutor.nombre}. Quedará en espera de revisión.")
                    registrar_auditoria(self.request.user, "Edición de Obra por Auxiliar", f"Auxiliar {self.request.user.username} reenvió obra corregida: {articulo.titulo} de su tutor {tutor.nombre}")
            else:
                messages.success(self.request, f"Los cambios en la obra del Dr. {tutor.nombre} han sido guardados exitosamente.")
                registrar_auditoria(self.request.user, "Edición de Obra por Auxiliar", f"Auxiliar {self.request.user.username} modificó la obra: {articulo.titulo} de su tutor {tutor.nombre}")

            try:
                MensajeInterno.objects.create(
                    remitente=self.request.user,
                    destinatario=tutor,
                    asunto=f"Obra editada por tu Auxiliar: {articulo.titulo}",
                    cuerpo=f"Tu Auxiliar de Investigación FCA, {mi_autor.nombre}, ha editado y actualizado los datos de la obra '{articulo.titulo}'.",
                    es_soporte=False
                )
            except Exception:
                pass
        else:
            if articulo.estado in ['rechazado', 'pendiente'] and not self.request.user.is_superuser:
                if es_confianza:
                    articulo.estado = 'aprobado'
                    articulo.es_subida_automatica = True
                    articulo.chequeado_por_moderador = False
                    articulo.motivo_rechazo = ''
                    articulo.moderado_por = None
                    messages.success(self.request, "Obra actualizada y publicada de forma directa gracias a tu Credencial de Confianza.")
                    registrar_auditoria(self.request.user, "Publicación Directa por Confianza (Edición)", f"Publicó directamente tras corrección: {articulo.titulo}")
                else:
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

        # Limpiar autores huérfanos que se hayan desvinculado de la obra
        try:
            limpiar_autores_huerfanos(minutos_gracia=0, excluir_ids=articulo.autor.values_list('id', flat=True))
        except Exception:
            pass

        # Generar invitación de coautoría para nuevos colegas añadidos con cuenta
        for aut in articulo.autor.all():
            if aut.usuario and aut.usuario != self.request.user and (not es_auxiliar or aut != tutor):
                inv, created = InvitacionCoautoria.objects.get_or_create(
                    articulo=articulo,
                    autor_invitado=aut,
                    defaults={
                        'invitado_por': self.request.user,
                        'estado': 'pendiente',
                        'mensaje': f"{self.request.user.get_full_name() or self.request.user.username} te ha acreditado como coautor en '{articulo.titulo}'."
                    }
                )
                if created:
                    try:
                        notificar_invitacion_coautoria(inv)
                    except Exception as e:
                        logger.warning(f"Error al enviar correo de invitación de coautoría: {e}")
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
        mi_autor = getattr(self.request.user, 'autor', None)
        if mi_autor and mi_autor.es_auxiliar and mi_autor.profesor_tutor and mi_autor.aprobado_por_tutor:
            context['es_auxiliar_delegado'] = True
            context['profesor_tutor'] = mi_autor.profesor_tutor
        return context


class BusquedaResultadosView(ListView):
    model = Articulo
    template_name = 'Resultados.html'
    context_object_name = 'articulos'
    paginate_by = 15  # <--- MEJORA 2: Paginación de 15 en 15

    def _filtrar_base(self, excluir=None):
        """Devuelve el queryset base de artículos aprobados aplicando todos los filtros activos EXCEPTO los indicados en `excluir`."""
        if excluir is None:
            excluir = set()

        q = self.request.GET.get('q', '').strip()
        tipo_id = self.request.GET.get('tipo', '').strip()
        entidad_id = self.request.GET.get('entidad', '').strip()
        area_filtro = self.request.GET.get('area', '').strip()
        anio_filtro = self.request.GET.get('anio', '').strip()
        filtro_atributo = self.request.GET.get('filtro_atributo', 'todo').strip().lower()

        resultados = Articulo.objects.filter(filtro_publico_articulos())

        if q:
            import re, unicodedata

            # Extraer frases entre comillas y palabras sueltas
            tokens = [t.strip(' "\'') for t in re.findall(r'\"[^\"]+\"|\S+', q) if t.strip(' "\'')]

            def _construir_q_token(tok):
                # Generar variantes con y sin acentos para que búsquedas como 'analisis' o 'análisis' funcionen igual
                tok_sin_acento = ''.join(
                    c for c in unicodedata.normalize('NFD', tok)
                    if unicodedata.category(c) != 'Mn'
                )
                variantes = {tok}
                if tok_sin_acento:
                    variantes.add(tok_sin_acento)

                q_token = Q()
                for v in variantes:
                    if filtro_atributo == 'titulos':
                        q_token |= Q(titulo__icontains=v)
                    elif filtro_atributo == 'autores':
                        q_token |= (
                            Q(autor__nombre__icontains=v) |
                            Q(asesor__nombre__icontains=v) |
                            Q(coasesor__nombre__icontains=v) |
                            Q(autor__codigo_institucional__icontains=v)
                        )
                    elif filtro_atributo == 'palabras_clave':
                        q_token |= Q(palabras_clave__icontains=v)
                    elif filtro_atributo == 'areas':
                        q_token |= Q(area__nombre__icontains=v)
                    elif filtro_atributo == 'tipos':
                        q_token |= Q(tipo_contenido__nombre__icontains=v)
                    else:  # 'todo'
                        cond = (
                            Q(titulo__icontains=v) |
                            Q(descripcion__icontains=v) |
                            Q(autor__nombre__icontains=v) |
                            Q(asesor__nombre__icontains=v) |
                            Q(coasesor__nombre__icontains=v) |
                            Q(tipo_contenido__nombre__icontains=v) |
                            Q(area__nombre__icontains=v) |
                            Q(palabras_clave__icontains=v) |
                            Q(idioma__icontains=v) |
                            Q(revista__icontains=v) |
                            Q(editorial__icontains=v) |
                            Q(carrera_o_posgrado__icontains=v) |
                            Q(grado_academico__icontains=v) |
                            Q(isbn_issn__icontains=v) |
                            Q(entidad__nombre__icontains=v) |
                            Q(autor__institucion_origen__icontains=v) |
                            Q(autor__codigo_institucional__icontains=v)
                        )
                        if v.isdigit() and len(v) == 4:
                            cond |= Q(año_produccion=int(v))
                        q_token |= cond
                return q_token

            if tokens:
                # 1. Intentar intersección (AND): Todas las palabras buscadas deben estar presentes en la obra
                q_and = Q()
                for tok in tokens:
                    q_and &= _construir_q_token(tok)

                resultados_and = resultados.filter(q_and).distinct()
                if resultados_and.exists():
                    resultados = resultados_and
                else:
                    # 2. Tolerancia a búsquedas relacionadas (OR): Si no coinciden todos los términos juntos,
                    # mostrar obras que coincidan con los términos para no dejar al usuario con 0 resultados vacíos
                    q_or = Q()
                    for tok in tokens:
                        q_or |= _construir_q_token(tok)
                    resultados = resultados.filter(q_or).distinct()

        if tipo_id and 'tipo' not in excluir:
            resultados = resultados.filter(tipo_contenido_id=tipo_id)
        if entidad_id and 'entidad' not in excluir:
            resultados = resultados.filter(entidad_id=entidad_id)
        if area_filtro and 'area' not in excluir:
            if area_filtro.isdigit():
                resultados = resultados.filter(area_id=area_filtro)
            else:
                resultados = resultados.filter(area__nombre__iexact=area_filtro)
        if anio_filtro and 'anio' not in excluir:
            resultados = resultados.filter(año_produccion=anio_filtro)

        return resultados.distinct()

    def get_queryset(self):
        return self._filtrar_base().prefetch_related(
            'autor', 'tipo_contenido', 'area', 'entidad'
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        articulos_aprobados = Articulo.objects.filter(filtro_publico_articulos())

        # 1. Facetas de Tipo de Contenido: Preservan todos los tipos existentes con producción,
        # calculando dinámicamente el conteo respecto a los demás filtros (q, área, año)
        articulos_sin_tipo = self._filtrar_base(excluir={'tipo'})
        tipos_con_produccion = TipoContenido.objects.filter(articulo__in=articulos_aprobados).distinct()
        context['tipos_contenido'] = tipos_con_produccion.annotate(
            total=Count('articulo', filter=Q(articulo__in=articulos_sin_tipo))
        ).order_by('-total', 'nombre')

        # 2. Facetas de Área Académica: Muestran las áreas pertinentes según el tipo de recurso seleccionado
        articulos_sin_area = self._filtrar_base(excluir={'area'})
        areas_con_produccion = Area.objects.filter(articulo__in=articulos_aprobados).distinct()
        context['areas_disponibles'] = areas_con_produccion.annotate(
            total=Count('articulo', filter=Q(articulo__in=articulos_sin_area))
        ).filter(total__gt=0).order_by('-total', 'nombre')

        # 3. Facetas de Año de Producción
        articulos_sin_anio = self._filtrar_base(excluir={'anio'})
        context['anios_disponibles'] = articulos_sin_anio.exclude(año_produccion__isnull=True).values(
            'año_produccion'
        ).annotate(total=Count('id')).order_by('-año_produccion')

        # 4. Facetas de Entidad
        articulos_sin_entidad = self._filtrar_base(excluir={'entidad'})
        entidades_con_produccion = Entidad.objects.filter(articulo__in=articulos_aprobados).distinct()
        context['entidades'] = entidades_con_produccion.annotate(
            total=Count('articulo', filter=Q(articulo__in=articulos_sin_entidad))
        ).order_by('-total', 'nombre')

        context['query_actual'] = self.request.GET.get('q', '')
        context['tipo_actual'] = self.request.GET.get('tipo', '')
        context['entidad_actual'] = self.request.GET.get('entidad', '')
        context['area_actual'] = self.request.GET.get('area', '')
        context['anio_actual'] = self.request.GET.get('anio', '')
        context['filtro_atributo_actual'] = self.request.GET.get('filtro_atributo', 'todo')

        context['total_documentos'] = articulos_aprobados.count()
        context['resultados_count'] = self.get_queryset().count()
        return context


# ==============================================================================
# AUTENTICACIÓN Y REGISTRO
# ==============================================================================

def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        login_input = request.POST.get('username', '').strip()
        pass_input = request.POST.get('password', '')

        # 1. Intentar verificar si el identificador corresponde a un usuario registrado
        usuario_encontrado = User.objects.filter(
            Q(username__iexact=login_input) | Q(email__iexact=login_input)
        ).first()

        if usuario_encontrado:
            # Si el usuario tiene cuenta inactiva o suspendida
            if not usuario_encontrado.is_active and hasattr(usuario_encontrado, 'autor') and usuario_encontrado.autor:
                autor = usuario_encontrado.autor
                clave_correcta = usuario_encontrado.check_password(pass_input)

                # Si tiene suspensión temporal expirada y clave correcta, reactivar automáticamente
                if clave_correcta and autor.estado_cuenta == 'suspendida' and autor.fecha_fin_suspension:
                    if timezone.now() >= autor.fecha_fin_suspension:
                        usuario_encontrado.is_active = True
                        usuario_encontrado.save()
                        autor.estado_cuenta = 'activa'
                        autor.motivo_suspension = ''
                        autor.fecha_fin_suspension = None
                        autor.fecha_suspension = None
                        autor.suspendido_por = None
                        autor.save()
                        login(request, usuario_encontrado)
                        messages.success(request, 'El periodo de suspensión ha finalizado. Tu cuenta ha sido reactivada exitosamente.')
                        return redirect('/')

                # Si ya tiene una solicitud de reactivación pendiente
                if autor.solicitud_reactivacion:
                    messages.info(
                        request,
                        'Ya cuentas con una solicitud de reactivación pendiente en el sistema. '
                        'El equipo de administración de FCA la revisará a la brevedad.'
                    )
                    return render(request, 'login.html', {
                        'form': AuthenticationForm(request),
                        'cuenta_inactiva_reactivable': True,
                        'usuario_intentado': usuario_encontrado.username,
                    })

                # Si está suspendida
                if autor.estado_cuenta == 'suspendida':
                    if autor.fecha_fin_suspension:
                        fin_str = timezone.localtime(autor.fecha_fin_suspension).strftime('%d/%m/%Y a las %H:%M hrs')
                        tiempo_info = f" hasta el {fin_str}"
                    else:
                        tiempo_info = " por tiempo indefinido"

                    motivo_info = f" Motivo: «{autor.motivo_suspension}»." if autor.motivo_suspension else ""
                    messages.warning(
                        request,
                        f'Tu cuenta se encuentra suspendida{tiempo_info}.{motivo_info} '
                        f'Si deseas solicitar su reactivación o aclaración, puedes enviar una solicitud a los administradores.'
                    )
                    return render(request, 'login.html', {
                        'form': AuthenticationForm(request),
                        'cuenta_inactiva_reactivable': True,
                        'usuario_intentado': usuario_encontrado.username,
                    })

                # Si es baja voluntaria
                elif autor.estado_cuenta == 'baja_voluntaria':
                    if clave_correcta:
                        messages.warning(
                            request,
                            'Esta cuenta fue dada de baja voluntariamente por el usuario. '
                            'Si deseas reactivarla y recuperar tu acceso, puedes enviar tu solicitud de reactivación ahora mismo.'
                        )
                    else:
                        messages.warning(
                            request,
                            'Esta cuenta fue dada de baja voluntariamente por su titular. '
                            'Si eres el propietario y deseas reactivarla, puedes enviar una solicitud directamente desde aquí.'
                        )
                    return render(request, 'login.html', {
                        'form': AuthenticationForm(request),
                        'cuenta_inactiva_reactivable': True,
                        'usuario_intentado': usuario_encontrado.username,
                    })

                # Cuenta pendiente de verificación de correo mediante código OTP
                elif autor.estado_cuenta == 'pendiente_verificacion':
                    messages.warning(
                        request,
                        'Tu cuenta aún requiere autenticar tu correo institucional. Ingresa el código de 6 dígitos que te enviamos.'
                    )
                    return redirect('verificar_codigo_registro', user_id=usuario_encontrado.id)

                # Cuenta en validación inicial
                elif autor.estado_cuenta == 'pendiente':
                    messages.info(
                        request,
                        'Tu solicitud de registro se encuentra en proceso de validación. '
                        'Recibirás acceso una vez que el administrador apruebe tu cuenta.'
                    )
                    return render(request, 'login.html', {'form': AuthenticationForm(request)})

            elif usuario_encontrado.check_password(pass_input) and not usuario_encontrado.is_active:
                messages.info(request, 'Tu cuenta está en espera de revisión por el administrador.')
                return render(request, 'login.html', {'form': AuthenticationForm(request)})

        # 2. Autenticación estándar a través de Django
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, 'Tu cuenta se encuentra inactiva o suspendida.')
                return render(request, 'login.html', {'form': form})
            login(request, user)
            return redirect('/')
        else:
            messages.error(request, 'Usuario/correo o contraseña incorrectos. Verifica tus credenciales.')
    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('/')


def solicitar_registro_view(request):
    if request.method == 'POST':
        tipo_personal = request.POST.get('tipo_personal', 'docente')
        nombres = request.POST.get('nombres', '').strip()
        apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apellido_materno = request.POST.get('apellido_materno', '').strip()
        nombre = request.POST.get('nombre', '').strip()

        # Armar nombre completo unificado
        if nombres and apellido_paterno:
            partes = [nombres, apellido_paterno]
            if apellido_materno:
                partes.append(apellido_materno)
            nombre_final = " ".join(partes)
        else:
            nombre_final = nombre or request.POST.get('nombre_completo', '').strip()

        username = request.POST.get('username', '').strip()
        correo = request.POST.get('correo', '').strip()
        if not username and correo:
            username = correo.split('@')[0]
        password = request.POST.get('password')
        fecha_nacimiento = (request.POST.get('fecha_nacimiento') or request.POST.get('nacimiento_fecha') or '').strip()
        genero = request.POST.get('genero', 'NE')
        numero_empleado = (
            request.POST.get('clave_empleado') or 
            request.POST.get('codigo_empleado') or 
            request.POST.get('num_empleado') or 
            request.POST.get('numero_empleado') or ''
        ).strip()

        institucion_final = "UABC"
        es_profesor = (tipo_personal in ['docente', 'externo', 'independiente'])
        es_externo = (tipo_personal in ['externo', 'independiente'])
        es_auxiliar = (tipo_personal == 'auxiliar')
        es_operador_tecnico = (tipo_personal == 'operador_tecnico')
        es_soporte = (tipo_personal == 'soporte')

        if es_auxiliar:
            rol_facultad_asignar = 'AUX_INV'
            tipo_perfil_nombre = 'Auxiliar de Investigación FCA'
        elif es_operador_tecnico:
            rol_facultad_asignar = 'DEP_TEC'
            tipo_perfil_nombre = 'Operador Técnico / Depurador de Contenidos'
            institucion_final = "FCA UABC - Cómputo y Digitalización"
        elif es_soporte:
            rol_facultad_asignar = 'SOPORTE'
            tipo_perfil_nombre = 'Soporte Técnico / Administración'
            institucion_final = "FCA UABC - Soporte y Administración"
        elif tipo_personal == 'independiente':
            rol_facultad_asignar = 'INV_IND'
            tipo_perfil_nombre = 'Investigador Independiente'
        elif tipo_personal == 'externo':
            rol_facultad_asignar = 'EXT'
            tipo_perfil_nombre = 'Investigador Colaborador Externo'
        else:
            rol_facultad_asignar = 'OTRO'
            tipo_perfil_nombre = 'Docente / Investigador UABC'

        profesor_tutor_id = request.POST.get('profesor_tutor_id')
        matricula_auxiliar = request.POST.get('matricula_auxiliar', '').strip()
        modalidad_auxiliar = request.POST.get('modalidad_auxiliar', 'Servicio Social Profesional (SSP)').strip()
        tutor_docente = None

        if tipo_personal == 'auxiliar':
            if not profesor_tutor_id:
                messages.error(request, 'Debes seleccionar al Profesor Titular / Responsable de la UABC al cual asistirás como Auxiliar de Investigación FCA.')
                unis = obtener_o_sincronizar_universidades()
                profesores_uabc = Autor.objects.filter(es_profesor=True, es_externo=False).order_by('nombre')
                return render(request, 'solicitar_registro.html', {'universidades': unis, 'profesores_uabc': profesores_uabc})
            tutor_docente = Autor.objects.filter(id=profesor_tutor_id, es_profesor=True, es_externo=False).first()
            institucion_final = f"FCA UABC (Tutor: {tutor_docente.nombre if tutor_docente else 'UABC'})"

        if tipo_personal in ['externo', 'independiente']:
            inst_sel = request.POST.get('institucion_existente', 'nueva').strip()
            nom_uni = request.POST.get('institucion_nombre', '').strip()
            sig_uni = request.POST.get('institucion_siglas', '').strip().upper()

            if nom_uni and sig_uni:
                Universidad.objects.get_or_create(
                    nombre__iexact=nom_uni,
                    defaults={'nombre': nom_uni, 'siglas': sig_uni}
                )

            if tipo_personal == 'independiente':
                if sig_uni:
                    institucion_final = f"Investigador Independiente ({sig_uni})"
                elif nom_uni:
                    institucion_final = f"Investigador Independiente ({nom_uni})"
                else:
                    institucion_final = "Investigador Independiente"
            else:
                if inst_sel != 'nueva' and inst_sel:
                    institucion_final = inst_sel
                elif nom_uni and sig_uni:
                    institucion_final = f"{nom_uni} ({sig_uni})"
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
            user.is_superuser = False
            user.save()

            # Búsqueda de autor prospectivo existente sin cuenta vinculada
            filtro_prospectivo = Q()
            if correo:
                filtro_prospectivo |= Q(correo__iexact=correo)
            if nombre_final:
                filtro_prospectivo |= Q(nombre__iexact=nombre_final)
            if nombres and apellido_paterno:
                filtro_prospectivo |= (Q(nombres__iexact=nombres) & Q(apellido_paterno__iexact=apellido_paterno))

            autor_existente = Autor.objects.filter(usuario__isnull=True).filter(
                filtro_prospectivo
            ).first() if filtro_prospectivo else None

            if autor_existente:
                autor_existente.usuario = user
                autor_existente.correo = correo
                if nombre_final:
                    autor_existente.nombre = nombre_final
                if nombres:
                    autor_existente.nombres = nombres
                if apellido_paterno:
                    autor_existente.apellido_paterno = apellido_paterno
                if apellido_materno:
                    autor_existente.apellido_materno = apellido_materno
                autor_existente.institucion_origen = institucion_final
                autor_existente.fecha_nacimiento = fecha_nacimiento if fecha_nacimiento else None
                autor_existente.genero = genero
                autor_existente.numero_empleado = numero_empleado if numero_empleado else None
                autor_existente.es_profesor = es_profesor
                autor_existente.es_externo = es_externo
                autor_existente.es_auxiliar = es_auxiliar
                autor_existente.es_operador_tecnico = es_operador_tecnico
                autor_existente.es_soporte = es_soporte
                autor_existente.rol_facultad = rol_facultad_asignar
                if es_auxiliar:
                    autor_existente.profesor_tutor = tutor_docente
                    autor_existente.matricula_estudiante = matricula_auxiliar
                    autor_existente.modalidad_auxiliar = modalidad_auxiliar
                    autor_existente.aprobado_por_tutor = False
                
                codigo_otp = f"{random.randint(100000, 999999)}"
                expira_otp = timezone.now() + timedelta(minutes=15)
                autor_existente.estado_cuenta = 'pendiente_verificacion'
                autor_existente.correo_verificado = False
                autor_existente.codigo_verificacion = codigo_otp
                autor_existente.codigo_verificacion_expira = expira_otp
                autor_existente.save()
                Nombramiento.objects.get_or_create(autor=autor_existente, rol=rol_facultad_asignar)
                autor_final_obj = autor_existente
            else:
                codigo_otp = f"{random.randint(100000, 999999)}"
                expira_otp = timezone.now() + timedelta(minutes=15)
                nuevo_autor = Autor.objects.create(
                    usuario=user,
                    nombre=nombre_final if nombre_final else username,
                    nombres=nombres if nombres else None,
                    apellido_paterno=apellido_paterno if apellido_paterno else None,
                    apellido_materno=apellido_materno if apellido_materno else None,
                    correo=correo,
                    institucion_origen=institucion_final,
                    fecha_nacimiento=fecha_nacimiento if fecha_nacimiento else None,
                    genero=genero,
                    numero_empleado=numero_empleado if numero_empleado else None,
                    es_profesor=es_profesor,
                    es_externo=es_externo,
                    es_auxiliar=es_auxiliar,
                    es_operador_tecnico=es_operador_tecnico,
                    es_soporte=es_soporte,
                    profesor_tutor=tutor_docente if es_auxiliar else None,
                    matricula_estudiante=matricula_auxiliar if es_auxiliar else None,
                    modalidad_auxiliar=modalidad_auxiliar if es_auxiliar else None,
                    aprobado_por_tutor=False if es_auxiliar else True,
                    rol_facultad=rol_facultad_asignar,
                    estado_cuenta='pendiente_verificacion',
                    correo_verificado=False,
                    codigo_verificacion=codigo_otp,
                    codigo_verificacion_expira=expira_otp,
                    estado_semblanza='borrador' if es_profesor else 'aprobado'
                )
                Nombramiento.objects.get_or_create(autor=nuevo_autor, rol=rol_facultad_asignar)
                autor_final_obj = nuevo_autor

            # Notificación interna al docente titular si es un auxiliar
            if es_auxiliar and tutor_docente:
                try:
                    MensajeInterno.objects.create(
                        remitente=user,
                        destinatario=tutor_docente,
                        asunto=f"Solicitud de Vinculación: Auxiliar de Investigación FCA ({nombre_final})",
                        cuerpo=f"El estudiante/prestador {nombre_final} (Matrícula: {matricula_auxiliar}, Modalidad: {modalidad_auxiliar}) te ha seleccionado como su Profesor Titular / Responsable en la FCA.\n\nPor favor ingresa a tu panel personal ('Mi Panel') para revisar y otorgar tu Visto Bueno.",
                        es_soporte=False
                    )
                except Exception:
                    pass

            # ENVÍO DE CÓDIGO DE AUTENTICACIÓN AL CORREO DEL SOLICITANTE (15 MINUTOS)
            try:
                notificar_codigo_verificacion_registro(user, codigo_otp)
            except Exception as e:
                logger.warning(f"Error al enviar código de verificación por correo: {e}")

            registrar_auditoria(None, "Solicitud de Cuenta con OTP",
                                f"Nueva solicitud de registro: {username} ({correo}) - Perfil: {tipo_perfil_nombre}. Código OTP de 6 dígitos generado (expira en 15 min).")

            messages.info(request, f'Hemos enviado un código de seguridad de 6 dígitos a {correo}. Tienes 15 minutos para ingresarlo y validar tu cuenta.')
            return redirect('verificar_codigo_registro', user_id=user.id)

    unis = obtener_o_sincronizar_universidades()
    profesores_uabc = Autor.objects.filter(es_profesor=True, es_externo=False, estado_cuenta='activa').order_by('nombre')
    return render(request, 'solicitar_registro.html', {'universidades': unis, 'profesores_uabc': profesores_uabc})


def verificar_codigo_registro_view(request, user_id):
    """Permite al nuevo solicitante verificar su correo ingresando el código OTP de 6 dígitos que expira en 15 minutos."""
    user = get_object_or_404(User, id=user_id)
    autor = getattr(user, 'autor', None)
    if not autor:
        messages.error(request, 'No se encontró el perfil de la cuenta.')
        return redirect('login')

    if autor.correo_verificado:
        messages.info(request, 'Tu correo institucional ya ha sido autenticado. Tu solicitud se encuentra en espera de aprobación por la administración.')
        return redirect('login')

    segundos_restantes = 0
    segundos_espera_desbloqueo = 300
    if autor.codigo_verificacion_expira:
        diff = (autor.codigo_verificacion_expira - timezone.now()).total_seconds()
        segundos_restantes = max(0, int(diff))
        # El código es válido por 15 min (900s). Los primeros 5 min corresponden a diff de 900 a 600.
        # Si diff <= 600, ya transcurrieron 5 min completos y el código de respaldo se desbloquea.
        segundos_espera_desbloqueo = max(0, int(diff - 600))

    if request.method == 'POST':
        codigo_ingresado = request.POST.get('codigo', '').strip()

        if autor.codigo_verificacion_expira and timezone.now() > autor.codigo_verificacion_expira:
            messages.error(request, 'El código de verificación ha expirado (límite de 15 minutos). Por favor solicita uno nuevo haciendo clic en «Reenviar Código».')
            return render(request, 'verificar_codigo.html', {
                'usuario': user,
                'segundos_restantes': 0,
                'segundos_espera_desbloqueo': 0,
                'codigo_demo': autor.codigo_verificacion,
            })

        if not autor.codigo_verificacion or codigo_ingresado != autor.codigo_verificacion:
            messages.error(request, 'El código ingresado es incorrecto. Por favor verifica el código de 6 dígitos enviado a tu correo.')
            return render(request, 'verificar_codigo.html', {
                'usuario': user,
                'segundos_restantes': segundos_restantes,
                'segundos_espera_desbloqueo': segundos_espera_desbloqueo,
                'codigo_demo': autor.codigo_verificacion,
            })

        # Determinar si la cuenta corresponde a un perfil docente autoactivable
        es_docente_autoactivable = autor.es_profesor and not (autor.es_auxiliar or autor.es_soporte or autor.es_operador_tecnico)

        # Código válido: marcar correo autenticado y liberar cuenta instantáneamente si es docente
        autor.correo_verificado = True
        autor.codigo_verificacion = None
        autor.codigo_verificacion_expira = None

        if es_docente_autoactivable:
            autor.estado_cuenta = 'activa'
            autor.save()
            user.is_active = True
            user.save()
        else:
            autor.estado_cuenta = 'pendiente'
            autor.save()

        # Determinar nombre descriptivo del perfil para las notificaciones
        if autor.es_auxiliar:
            tipo_perfil_nombre = 'Auxiliar de Investigación FCA'
        elif autor.es_operador_tecnico:
            tipo_perfil_nombre = 'Operador Técnico / Depurador de Contenidos'
        elif autor.es_soporte:
            tipo_perfil_nombre = 'Soporte Técnico / Administración'
        elif autor.rol_facultad == 'INV_IND':
            tipo_perfil_nombre = 'Investigador Independiente'
        elif autor.es_externo:
            tipo_perfil_nombre = 'Investigador Colaborador Externo'
        else:
            tipo_perfil_nombre = 'Docente / Investigador UABC'

        # Envío formal de correos de acuse al usuario y notificación al Super Admin
        try:
            if es_docente_autoactivable:
                from .emails import notificar_aprobacion_cuenta
                notificar_aprobacion_cuenta(user, tipo_perfil_nombre)
                notificar_solicitud_registro_admins(user, autor.nombre, f"{tipo_perfil_nombre} (Activación Automática)")
            else:
                notificar_solicitud_registro_usuario(user, autor.nombre, tipo_perfil_nombre)
                notificar_solicitud_registro_admins(user, autor.nombre, tipo_perfil_nombre)
                if autor.es_auxiliar and autor.profesor_tutor:
                    notificar_solicitud_tutor_auxiliar(autor, autor.profesor_tutor)
        except Exception as e:
            logger.warning(f"Error al enviar correos tras verificación OTP: {e}")

        if es_docente_autoactivable:
            registrar_auditoria(None, "Liberación Instantánea de Cuenta Docente",
                                f"El docente {user.username} ({user.email}) autenticó su correo mediante código OTP y su cuenta fue activada automáticamente sin requerir aprobación manual del Super Admin.")
            messages.success(request, '¡Correo verificado con éxito! Tu cuenta docente ha sido liberada y activada automáticamente. Ya puedes iniciar sesión ahora mismo con tus credenciales.')
        elif autor.es_auxiliar:
            registrar_auditoria(None, "Autenticación de Correo Exitosa",
                                f"El usuario {user.username} ({user.email}) autenticó exitosamente su correo mediante código OTP.")
            messages.success(request, f'¡Correo autenticado exitosamente! Tu profesor tutor ({autor.profesor_tutor.nombre if autor.profesor_tutor else "Docente FCA"}) revisará tu solicitud para otorgar su Visto Bueno antes de la activación.')
        elif autor.es_soporte:
            registrar_auditoria(None, "Autenticación de Correo Exitosa",
                                f"El usuario {user.username} ({user.email}) autenticó exitosamente su correo mediante código OTP.")
            messages.success(request, '¡Correo autenticado exitosamente! Tu cuenta de Soporte Técnico pasará al Administrador Principal para otorgar los privilegios correspondientes.')
        elif autor.es_operador_tecnico:
            registrar_auditoria(None, "Autenticación de Correo Exitosa",
                                f"El usuario {user.username} ({user.email}) autenticó exitosamente su correo mediante código OTP.")
            messages.success(request, '¡Correo autenticado exitosamente! Tu cuenta de Operador Técnico ha quedado enviada a revisión por la administración.')
        else:
            registrar_auditoria(None, "Autenticación de Correo Exitosa",
                                f"El usuario {user.username} ({user.email}) autenticó exitosamente su correo mediante código OTP.")
            messages.success(request, '¡Correo autenticado exitosamente! Tu solicitud de cuenta ha sido enviada al Administrador para su aprobación.')

        return redirect('login')

    return render(request, 'verificar_codigo.html', {
        'usuario': user,
        'segundos_restantes': segundos_restantes,
        'segundos_espera_desbloqueo': segundos_espera_desbloqueo,
        'codigo_demo': autor.codigo_verificacion,
    })


def reenviar_codigo_registro_view(request, user_id):
    """Genera y reenvía un nuevo código OTP de 6 dígitos válido por 15 minutos."""
    user = get_object_or_404(User, id=user_id)
    autor = getattr(user, 'autor', None)
    if not autor:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('login')

    if autor.correo_verificado:
        messages.info(request, 'Tu correo institucional ya ha sido autenticado.')
        return redirect('login')

    nuevo_codigo = f"{random.randint(100000, 999999)}"
    autor.codigo_verificacion = nuevo_codigo
    autor.codigo_verificacion_expira = timezone.now() + timedelta(minutes=15)
    autor.save()

    try:
        notificar_codigo_verificacion_registro(user, nuevo_codigo)
        messages.success(request, f'Se ha generado y enviado un nuevo código de seguridad a {user.email}. Tienes 15 minutos para ingresarlo.')
    except Exception as e:
        logger.error(f"Error al reenviar código: {e}")
        messages.error(request, 'Ocurrió un error al enviar el correo. Por favor intenta de nuevo.')

    return redirect('verificar_codigo_registro', user_id=user.id)


def recuperar_password_view(request):
    """Paso 1: Solicitud de código OTP para restablecimiento de contraseña olvidada."""
    if request.user.is_authenticated:
        return redirect('/')

    if request.method == 'POST':
        identificador = request.POST.get('identificador', '').strip()
        usuario = User.objects.filter(
            Q(username__iexact=identificador) | Q(email__iexact=identificador)
        ).first()

        if not usuario or not usuario.email:
            messages.error(request, 'No se encontró ninguna cuenta asociada al correo o usuario ingresado.')
            return render(request, 'recuperar_password.html', {'paso': 1})

        autor = getattr(usuario, 'autor', None)
        if not autor:
            messages.error(request, 'La cuenta no tiene un perfil institucional asociado.')
            return render(request, 'recuperar_password.html', {'paso': 1})

        codigo_rec = f"{random.randint(100000, 999999)}"
        autor.codigo_recuperacion = codigo_rec
        autor.codigo_recuperacion_expira = timezone.now() + timedelta(minutes=15)
        autor.save()

        try:
            notificar_codigo_recuperacion_password(usuario, codigo_rec)
            messages.success(request, f'Hemos enviado un código de seguridad de 6 dígitos a {usuario.email}. Ingrésalo a continuación.')
        except Exception as e:
            logger.error(f"Error al enviar código de recuperación: {e}")
            messages.error(request, 'No se pudo enviar el correo de recuperación. Intenta más tarde.')
            return render(request, 'recuperar_password.html', {'paso': 1})

        return render(request, 'recuperar_password.html', {'paso': 2, 'usuario': usuario})

    return render(request, 'recuperar_password.html', {'paso': 1})


def validar_recuperar_password_view(request, user_id):
    """Paso 2: Validación de código OTP (15 min) y cambio seguro de contraseña."""
    usuario = get_object_or_404(User, id=user_id)
    autor = getattr(usuario, 'autor', None)

    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip()
        nueva_password = request.POST.get('nueva_password', '').strip()
        confirmar_password = request.POST.get('confirmar_password', '').strip()

        if not autor or not autor.codigo_recuperacion:
            messages.error(request, 'No hay ninguna solicitud de recuperación activa para esta cuenta.')
            return redirect('recuperar_password')

        if autor.codigo_recuperacion_expira and timezone.now() > autor.codigo_recuperacion_expira:
            messages.error(request, 'El código de seguridad ha expirado (límite de 15 minutos). Solicita uno nuevo.')
            return render(request, 'recuperar_password.html', {'paso': 2, 'usuario': usuario})

        if codigo != autor.codigo_recuperacion:
            messages.error(request, 'El código ingresado es incorrecto. Verifica el código enviado a tu correo.')
            return render(request, 'recuperar_password.html', {'paso': 2, 'usuario': usuario})

        if len(nueva_password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
            return render(request, 'recuperar_password.html', {'paso': 2, 'usuario': usuario})

        if nueva_password != confirmar_password:
            messages.error(request, 'Las contraseñas no coinciden. Por favor verifica e intenta de nuevo.')
            return render(request, 'recuperar_password.html', {'paso': 2, 'usuario': usuario})

        usuario.set_password(nueva_password)
        usuario.save()

        autor.codigo_recuperacion = None
        autor.codigo_recuperacion_expira = None
        autor.save()

        try:
            notificar_alerta_cambio_password(usuario)
        except Exception as e:
            logger.warning(f"Error al enviar alerta de cambio de contraseña: {e}")

        registrar_auditoria(usuario, "Recuperación de Contraseña Exitosa",
                            f"El usuario {usuario.username} restableció su contraseña exitosamente mediante código OTP.")

        messages.success(request, '¡Tu contraseña ha sido restablecida con éxito! Ya puedes iniciar sesión con tu nueva contraseña.')
        return redirect('login')

    return redirect('recuperar_password')


# ==============================================================================
# PANEL PROPIO DEL DOCENTE / ACTUALIZAR PERFIL
# ==============================================================================

@login_required
def mi_panel_view(request):
    # <--- MEJORA 2: Paginación en Paneles con Búsqueda Global en BD --->
    q_subidas = request.GET.get('q_subidas', '').strip()
    mis_subidas_qs = Articulo.objects.filter(subido_por=request.user).order_by('-created_at')
    if q_subidas:
        mis_subidas_qs = mis_subidas_qs.filter(
            Q(titulo__icontains=q_subidas) |
            Q(tipo_contenido__nombre__icontains=q_subidas) |
            Q(area__nombre__icontains=q_subidas) |
            Q(palabras_clave__icontains=q_subidas) |
            Q(editorial__icontains=q_subidas) |
            Q(carrera_o_posgrado__icontains=q_subidas)
        ).distinct()

    paginator_subidas = Paginator(mis_subidas_qs, 20)
    page_subidas = request.GET.get('page_subidas')
    mis_subidas = paginator_subidas.get_page(page_subidas)

    q_coautorias = request.GET.get('q_coautorias', '').strip()
    mis_coautorias_qs = Articulo.objects.filter(autor__usuario=request.user).exclude(
        subido_por=request.user).distinct().order_by('-created_at')
    if q_coautorias:
        mis_coautorias_qs = mis_coautorias_qs.filter(
            Q(titulo__icontains=q_coautorias) |
            Q(tipo_contenido__nombre__icontains=q_coautorias) |
            Q(area__nombre__icontains=q_coautorias) |
            Q(subido_por__username__icontains=q_coautorias) |
            Q(subido_por__first_name__icontains=q_coautorias) |
            Q(subido_por__last_name__icontains=q_coautorias)
        ).distinct()

    paginator_coautorias = Paginator(mis_coautorias_qs, 20)
    page_coautorias = request.GET.get('page_coautorias')
    mis_coautorias = paginator_coautorias.get_page(page_coautorias)

    # Obtención de felicitaciones si el usuario tiene perfil Autor
    mensajes_cumpleanos = []
    es_mi_cumpleanos = False
    if hasattr(request.user, 'autor') and request.user.autor:
        mensajes_cumpleanos = request.user.autor.mensajes_recibidos.all().order_by('-fecha_envio')
        es_mi_cumpleanos = request.user.autor.es_cumpleanos_hoy

    # Detección de colegas (docentes UABC, otras universidades, investigadores) que cumplen años hoy (excluyendo al usuario actual)
    hoy = timezone.localdate()
    cumpleaneros_qs = Autor.objects.filter(
        fecha_nacimiento__isnull=False,
        fecha_nacimiento__day=hoy.day,
        fecha_nacimiento__month=hoy.month
    ).filter(
        Q(es_profesor=True) | Q(es_externo=True) | Q(rol_facultad='INV_IND')
    )
    if hasattr(request.user, 'autor') and request.user.autor:
        cumpleaneros_qs = cumpleaneros_qs.exclude(id=request.user.autor.id)

    cumpleaneros_hoy = list(cumpleaneros_qs)

    # Respaldo en Python si la base de datos no evaluó los filtros __day y __month
    if not cumpleaneros_hoy:
        todos_profes = Autor.objects.filter(fecha_nacimiento__isnull=False).filter(
            Q(es_profesor=True) | Q(es_externo=True) | Q(rol_facultad='INV_IND')
        )
        if hasattr(request.user, 'autor') and request.user.autor:
            todos_profes = todos_profes.exclude(id=request.user.autor.id)
        cumpleaneros_hoy = [p for p in todos_profes if getattr(p, 'es_cumpleanos_hoy', False)]

    # Roles y nombramientos del usuario
    mi_autor = getattr(request.user, 'autor', None)
    mis_roles_codigos = []
    cargo_custom_actual = ''
    cargos_custom_actuales = []

    if mi_autor:
        if not mi_autor.nombres and mi_autor.nombre:
            partes = mi_autor.nombre.strip().split()
            prefijos_conocidos = ['dr.', 'dr', 'dra.', 'dra', 'mtro.', 'mtro', 'mtra.', 'mtra', 'lic.', 'lic', 'ing.', 'ing', 'ph.d.', 'phd']
            if partes and partes[0].lower() in prefijos_conocidos:
                if not mi_autor.titulo_academico:
                    mi_autor.titulo_academico = partes.pop(0)
                else:
                    partes.pop(0)

            if len(partes) >= 3:
                mi_autor.nombres = " ".join(partes[:-2])
                mi_autor.apellido_paterno = partes[-2]
                mi_autor.apellido_materno = partes[-1]
            elif len(partes) == 2:
                mi_autor.nombres = partes[0]
                mi_autor.apellido_paterno = partes[1]
            elif len(partes) == 1:
                mi_autor.nombres = partes[0]
            try:
                mi_autor.save(update_fields=['nombres', 'apellido_paterno', 'apellido_materno', 'titulo_academico'])
            except Exception:
                pass

        mis_roles_codigos = list(mi_autor.nombramientos.values_list('rol', flat=True))
        cargos_custom_actuales = list(mi_autor.nombramientos.filter(rol='CUSTOM').exclude(cargo_personalizado__isnull=True).exclude(cargo_personalizado='').values_list('cargo_personalizado', flat=True))
        if cargos_custom_actuales:
            cargo_custom_actual = cargos_custom_actuales[0]

    mis_auxiliares = None
    auxiliares_pendientes_visto_bueno = None
    auxiliares_activos = None
    if mi_autor and mi_autor.es_profesor:
        mis_auxiliares = mi_autor.auxiliares_asignados.all().order_by('-created_at')
        auxiliares_pendientes_visto_bueno = mis_auxiliares.filter(aprobado_por_tutor=False)
        auxiliares_activos = mis_auxiliares.filter(aprobado_por_tutor=True)

    tutor_obras = None
    tutor_total_aprobadas = 0
    tutor_total_pendientes = 0
    tutor_total_rechazadas = 0
    tutor_autor = None

    if mi_autor and mi_autor.es_auxiliar and mi_autor.profesor_tutor and mi_autor.aprobado_por_tutor:
        tutor_autor = mi_autor.profesor_tutor
        filtro_tutor = Q(autor=tutor_autor)
        if tutor_autor.usuario:
            filtro_tutor |= Q(subido_por=tutor_autor.usuario)
        tutor_obras_qs = Articulo.objects.filter(filtro_tutor).distinct().order_by('-created_at')
        tutor_total_aprobadas = tutor_obras_qs.filter(estado='aprobado').count()
        tutor_total_pendientes = tutor_obras_qs.filter(estado='pendiente').count()
        tutor_total_rechazadas = tutor_obras_qs.filter(estado='rechazado').count()
        tutor_obras = tutor_obras_qs

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
        'roles_docente': ROL_DOCENTE_OPCIONES,
        'mis_roles_codigos': mis_roles_codigos,
        'cargo_custom_actual': cargo_custom_actual,
        'cargos_custom_actuales': cargos_custom_actuales,
        'q_subidas': q_subidas,
        'q_coautorias': q_coautorias,
        'mis_auxiliares': mis_auxiliares,
        'auxiliares_pendientes_visto_bueno': auxiliares_pendientes_visto_bueno,
        'auxiliares_activos': auxiliares_activos,
        'tutor_obras': tutor_obras,
        'tutor_total_aprobadas': tutor_total_aprobadas,
        'tutor_total_pendientes': tutor_total_pendientes,
        'tutor_total_rechazadas': tutor_total_rechazadas,
        'tutor_autor': tutor_autor,
        'es_soporte_modo_lector': bool(not request.user.is_superuser and mi_autor and (getattr(mi_autor, 'es_soporte', False) or mi_autor.rol_facultad == 'SOPORTE')),
        'es_operador_tecnico': bool(mi_autor and (getattr(mi_autor, 'es_operador_tecnico', False) or mi_autor.rol_facultad == 'DEP_TEC')),
    }
    return render(request, 'mi_panel.html', context)


@login_required
def actualizar_perfil_docente_view(request):
    if request.method == 'POST':
        target_autor_id = request.POST.get('target_autor_id', '').strip()
        mi_autor = getattr(request.user, 'autor', None)
        es_edicion_tutor = False
        tutor_editado = None

        if target_autor_id and mi_autor and mi_autor.es_auxiliar and mi_autor.profesor_tutor and mi_autor.aprobado_por_tutor:
            if str(mi_autor.profesor_tutor.id) == str(target_autor_id):
                autor = mi_autor.profesor_tutor
                es_edicion_tutor = True
                tutor_editado = autor
            else:
                messages.error(request, 'No tienes autorización para editar el perfil de este docente.')
                return redirect('mi_panel')
        elif hasattr(request.user, 'autor'):
            autor = request.user.autor
        else:
            nombre_temp = request.POST.get('nombre', '').strip()
            autor = Autor.objects.filter(nombre__iexact=nombre_temp).first()
            if not autor:
                autor = Autor.objects.create(usuario=request.user, nombre=nombre_temp or request.user.username)
            else:
                autor.usuario = request.user

        foto_personal_subida = request.FILES.get('foto_personal')
        if foto_personal_subida and 'nombre' not in request.POST and 'nombres' not in request.POST:
            autor.foto_personal = foto_personal_subida
            autor.save()
            messages.success(request, 'Tu foto de perfil personal ha sido actualizada.')
            return redirect('mi_panel')

        titulo_academico = request.POST.get('titulo_academico', '').strip()
        nombres = request.POST.get('nombres', '').strip()
        apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apellido_materno = request.POST.get('apellido_materno', '').strip()
        nombre = request.POST.get('nombre', '').strip()

        partes_oficiales = []
        if nombres:
            partes_oficiales.append(nombres)
        if apellido_paterno:
            partes_oficiales.append(apellido_paterno)
        if apellido_materno:
            partes_oficiales.append(apellido_materno)

        autor.titulo_academico = titulo_academico
        if nombres and apellido_paterno:
            autor.nombre = " ".join(partes_oficiales)
            autor.nombres = nombres
            autor.apellido_paterno = apellido_paterno
            autor.apellido_materno = apellido_materno
        elif nombre:
            autor.nombre = nombre

        if 'orcid' in request.POST:
            autor.orcid = request.POST.get('orcid', '').strip()

        genero = request.POST.get('genero', 'NE')
        genero_otro = request.POST.get('genero_otro', '').strip()
        cargos_seleccionados = request.POST.getlist('roles_facultad')

        biografia = request.POST.get('biografia', '').strip()
        # Semblanza enriquecida generada por Quill.js (mantiene etiquetas HTML)
        biografia_extendida = request.POST.get('biografia_extendida', '').strip()

        foto_claustro = request.FILES.get('foto_perfil')
        reconocimiento_pdf = request.FILES.get('reconocimiento_pdf')
        horario_pdf = request.FILES.get('horario_pdf')
        desea_horario = request.POST.get('desea_horario', 'si')
        eliminar_horario = request.POST.get('eliminar_horario', '0') == '1'
        eliminar_reconocimiento = request.POST.get('eliminar_reconocimiento', '0') == '1'

        enviar_a_moderacion = 'accion_enviar' in request.POST
        guardar_borrador = 'accion_borrador' in request.POST

        autor.genero = genero
        autor.genero_otro = genero_otro
        # Preservar la categoría e identidad principal del autor para que nunca se cambie a Docente UABC accidentalmente
        es_independiente_autor = (
            autor.rol_facultad == 'INV_IND' or
            'independiente' in (autor.institucion_origen or '').lower() or
            'INV_IND' in cargos_seleccionados
        )
        es_externo_autor = (
            autor.es_externo or
            autor.rol_facultad == 'EXT' or
            'EXT' in cargos_seleccionados or
            (autor.institucion_origen and autor.institucion_origen.upper() != 'UABC')
        )

        if es_independiente_autor:
            autor.rol_facultad = 'INV_IND'
            autor.es_profesor = True
            autor.es_externo = False
        elif es_externo_autor:
            autor.rol_facultad = 'EXT' if 'EXT' in cargos_seleccionados else (cargos_seleccionados[0] if cargos_seleccionados else 'EXT')
            autor.es_externo = True
            autor.es_profesor = True
        elif cargos_seleccionados:
            autor.rol_facultad = cargos_seleccionados[0]
        else:
            autor.rol_facultad = 'OTRO'

        # Actualización de semblanzas (borrador o envío)
        autor.biografia_borrador = biografia
        autor.biografia_extendida_borrador = biografia_extendida

        if foto_claustro:
            autor.foto_perfil_borrador = foto_claustro

        if eliminar_reconocimiento:
            autor.reconocimiento_pdf = None
            autor.reconocimiento_pdf_borrador = None
        elif reconocimiento_pdf:
            autor.reconocimiento_pdf_borrador = reconocimiento_pdf

        # El Horario Escolar Oficial solo aplica a Docentes de la UABC (no a colaboradores externos ni investigadores independientes)
        if autor.es_externo or autor.rol_facultad == 'INV_IND':
            autor.horario_pdf = None
            autor.horario_pdf_borrador = None
        elif desea_horario == 'no' or eliminar_horario:
            autor.horario_pdf = None
            autor.horario_pdf_borrador = None
        elif horario_pdf:
            autor.horario_pdf_borrador = horario_pdf

        if guardar_borrador:
            if es_edicion_tutor:
                messages.success(request, f'Has guardado los cambios en la semblanza del Dr. {autor.nombre} como borrador.')
                registrar_auditoria(request.user, "Actualización de Semblanza de Tutor (Borrador)", f"Auxiliar {request.user.username} guardó borrador de semblanza de {autor.nombre}")
                try:
                    MensajeInterno.objects.create(
                        remitente=request.user,
                        destinatario=autor,
                        asunto="Borrador de semblanza guardado por tu Auxiliar",
                        cuerpo=f"Tu Auxiliar de Investigación FCA, {mi_autor.nombre}, ha actualizado el borrador de tu semblanza académica.",
                        es_soporte=False
                    )
                except Exception:
                    pass
            else:
                messages.success(request, 'Tus cambios se han guardado como borrador privado.')
        elif enviar_a_moderacion:
            autor.estado_semblanza = 'pendiente'
            autor.perfil_completado = False
            autor.motivo_rechazo_semblanza = ''
            autor.moderado_por_semblanza = None
            if es_edicion_tutor:
                registrar_auditoria(request.user, "Envío de Semblanza de Tutor", f"Auxiliar {request.user.username} envió la semblanza de {autor.nombre} a revisión.")
                messages.info(request, f'La semblanza actualizada del Dr. {autor.nombre} ha sido enviada a moderación.')
                try:
                    MensajeInterno.objects.create(
                        remitente=request.user,
                        destinatario=autor,
                        asunto="Semblanza enviada a moderación por tu Auxiliar",
                        cuerpo=f"Tu Auxiliar de Investigación FCA, {mi_autor.nombre}, ha enviado tu semblanza académica actualizada a revisión institucional.",
                        es_soporte=False
                    )
                except Exception:
                    pass
            else:
                registrar_auditoria(request.user, "Envío de Semblanza", f"Envió su semblanza a revisión: {autor.nombre}")
                messages.info(request, 'Tu semblanza actualizada ha sido enviada a moderación.')

        autor.save()

        autor.nombramientos.all().delete()
        cargos_personalizados = request.POST.getlist('cargos_personalizados[]')
        cargo_personalizado_val = request.POST.get('cargo_personalizado', '').strip()
        if not cargos_personalizados and cargo_personalizado_val:
            cargos_personalizados = [cargo_personalizado_val]

        for rol_codigo in cargos_seleccionados:
            if rol_codigo == 'CUSTOM':
                for cp in cargos_personalizados:
                    cp_limpio = cp.strip()
                    if cp_limpio:
                        Nombramiento.objects.create(autor=autor, rol='CUSTOM', cargo_personalizado=cp_limpio)
            else:
                Nombramiento.objects.create(autor=autor, rol=rol_codigo)

        # Garantizar que el autor independiente siempre tenga el nombramiento de Investigador Independiente
        if es_independiente_autor and not autor.nombramientos.filter(rol='INV_IND').exists():
            Nombramiento.objects.create(autor=autor, rol='INV_IND')

        # Garantizar que el autor externo siempre tenga el nombramiento de Colaborador Externo
        if es_externo_autor and not autor.nombramientos.filter(rol='EXT').exists():
            Nombramiento.objects.create(autor=autor, rol='EXT')

        autor.enlaces_profesionales.all().delete()
        plataformas = request.POST.getlist('enlace_plataforma[]')
        urls = request.POST.getlist('enlace_url[]')
        emojis = request.POST.getlist('enlace_emoji[]')

        for plat, u, em in zip(plataformas, urls, emojis):
            p_text = plat.strip()
            u_text = u.strip()
            if p_text and u_text:
                if not u_text.startswith(('http://', 'https://')):
                    u_text = 'https://' + u_text
                em_text = em.strip()[:20] if em.strip() else '🔗'
                EnlaceProfesional.objects.create(
                    autor=autor,
                    plataforma=p_text,
                    url=u_text,
                    emoji=em_text
                )

    return redirect('mi_panel')


# ==============================================================================
# MÓDULO 5: GESTIÓN DE COAUTORÍAS Y MENSAJERÍA ACADÉMICA / SOPORTE
# ==============================================================================

@login_required
def gestion_coautorias_view(request):
    """
    Vista integral y dedicada para la gestión de Coautorías e Invitaciones Académicas.
    Soporta visualización delegada para Auxiliares de Investigación FCA vinculados a un profesor tutor.
    """
    mi_autor = getattr(request.user, 'autor', None)

    pendientes = []
    aceptadas = []
    rechazadas = []
    enviadas = []
    
    es_auxiliar_delegado = False
    mi_tutor = None

    if mi_autor:
        autores_para_coautoria = [mi_autor]
        if mi_autor.es_auxiliar and mi_autor.profesor_tutor and mi_autor.aprobado_por_tutor:
            es_auxiliar_delegado = True
            mi_tutor = mi_autor.profesor_tutor
            autores_para_coautoria.append(mi_tutor)

        pendientes = list(InvitacionCoautoria.objects.filter(
            autor_invitado__in=autores_para_coautoria,
            estado='pendiente'
        ).select_related('articulo', 'articulo__tipo_contenido', 'invitado_por', 'invitado_por__autor', 'autor_invitado'))

        aceptadas = list(InvitacionCoautoria.objects.filter(
            autor_invitado__in=autores_para_coautoria,
            estado='aceptada'
        ).select_related('articulo', 'articulo__tipo_contenido', 'invitado_por', 'invitado_por__autor', 'autor_invitado'))

        rechazadas = list(InvitacionCoautoria.objects.filter(
            autor_invitado__in=autores_para_coautoria,
            estado='rechazada'
        ).select_related('articulo', 'articulo__tipo_contenido', 'invitado_por', 'invitado_por__autor', 'autor_invitado'))

    # Solicitudes enviadas por este usuario a otros autores
    enviadas = list(InvitacionCoautoria.objects.filter(
        invitado_por=request.user
    ).select_related('articulo', 'articulo__tipo_contenido', 'autor_invitado'))

    context = {
        'mi_autor': mi_autor,
        'pendientes': pendientes,
        'aceptadas': aceptadas,
        'rechazadas': rechazadas,
        'enviadas': enviadas,
        'total_pendientes': len(pendientes),
        'total_aceptadas': len(aceptadas),
        'total_rechazadas': len(rechazadas),
        'total_enviadas': len(enviadas),
        'es_auxiliar_delegado': es_auxiliar_delegado,
        'mi_tutor': mi_tutor,
    }
    return render(request, 'coautorias.html', context)


@login_required
def responder_invitacion_coautoria_view(request, invitacion_id):
    """Permite al docente o a su auxiliar delegado aceptar, declinar o reconsiderar una solicitud de coautoría."""
    invitacion = get_object_or_404(InvitacionCoautoria, id=invitacion_id)
    mi_autor = getattr(request.user, 'autor', None)

    es_propia = bool(mi_autor and invitacion.autor_invitado == mi_autor)
    es_delegada_tutor = bool(
        mi_autor and 
        mi_autor.es_auxiliar and 
        mi_autor.aprobado_por_tutor and 
        mi_autor.profesor_tutor and 
        invitacion.autor_invitado == mi_autor.profesor_tutor
    )

    if not (es_propia or es_delegada_tutor):
        messages.error(request, 'No tienes permiso para gestionar esta invitación.')
        return redirect('gestion_coautorias')

    autor_objetivo = mi_autor.profesor_tutor if es_delegada_tutor else mi_autor

    if request.method == 'POST':
        accion = request.POST.get('accion')
        next_url = request.POST.get('next') or request.GET.get('next')

        if accion == 'aceptar':
            invitacion.estado = 'aceptada'
            invitacion.fecha_respuesta = timezone.now()
            invitacion.save()
            invitacion.articulo.autor.add(autor_objetivo)
            if es_delegada_tutor:
                registrar_auditoria(request.user, "Aceptación de Coautoría por Auxiliar", f"Auxiliar {request.user.username} confirmó coautoría en '{invitacion.articulo.titulo}' para su tutor {autor_objetivo.nombre}")
                try:
                    MensajeInterno.objects.create(
                        remitente=request.user,
                        destinatario=autor_objetivo,
                        asunto=f"Coautoría confirmada por tu Auxiliar: {invitacion.articulo.titulo}",
                        cuerpo=f"Tu Auxiliar de Investigación FCA, {mi_autor.nombre}, ha confirmado tu participación como coautor en la obra '{invitacion.articulo.titulo}'.",
                        es_soporte=False
                    )
                except Exception:
                    pass
                messages.success(request, f'Has confirmado la coautoría en "{invitacion.articulo.titulo}" en representación del Dr. {autor_objetivo.nombre}.')
            else:
                messages.success(request, f'¡Enhorabuena! Has confirmado tu coautoría en la obra "{invitacion.articulo.titulo}".')
        elif accion == 'rechazar':
            invitacion.estado = 'rechazada'
            invitacion.fecha_respuesta = timezone.now()
            invitacion.save()
            invitacion.articulo.autor.remove(autor_objetivo)
            if es_delegada_tutor:
                registrar_auditoria(request.user, "Rechazo de Coautoría por Auxiliar", f"Auxiliar {request.user.username} declinó coautoría en '{invitacion.articulo.titulo}' para su tutor {autor_objetivo.nombre}")
                try:
                    MensajeInterno.objects.create(
                        remitente=request.user,
                        destinatario=autor_objetivo,
                        asunto=f"Coautoría declinada por tu Auxiliar: {invitacion.articulo.titulo}",
                        cuerpo=f"Tu Auxiliar de Investigación FCA, {mi_autor.nombre}, ha declinado la invitación de coautoría en la obra '{invitacion.articulo.titulo}'.",
                        es_soporte=False
                    )
                except Exception:
                    pass
                messages.info(request, f'Has declinado la coautoría en "{invitacion.articulo.titulo}" en representación de tu tutor.')
            else:
                messages.info(request, f'Has declinado figurar como coautor en "{invitacion.articulo.titulo}". La invitación se ha archivado por si deseas reconsiderar en el futuro.')

        # Notificar por correo electrónico al autor que envió la invitación
        try:
            notificar_respuesta_coautoria(invitacion)
        except Exception as e:
            logger.warning(f"Error al enviar correo de respuesta de coautoría: {e}")

        if next_url:
            return redirect(next_url)
        return redirect('gestion_coautorias')

    return redirect('gestion_coautorias')


@login_required
def mensajeria_view(request):
    """
    Centro de Mensajería Académica entre Colegas del Claustro FCA.
    Exclusivo para comunicación directa entre docentes, investigadores y colaboradores externos.
    """
    mi_autor = getattr(request.user, 'autor', None)
    contacto_id = request.GET.get('contacto')

    # =========================================================================
    # 1. LISTA DE CONVERSACIONES DIRECTAS ENTRE AUTORES
    # =========================================================================
    conversaciones_directas = []
    autores_interactuados = set()

    autores_enviados = MensajeInterno.objects.filter(
        remitente=request.user,
        es_soporte=False,
        destinatario__isnull=False
    ).values_list('destinatario_id', flat=True).distinct()
    autores_interactuados.update(autores_enviados)

    if mi_autor:
        autores_recibidos = MensajeInterno.objects.filter(
            destinatario=mi_autor,
            es_soporte=False
        ).values_list('remitente__autor', flat=True).distinct()
        autores_interactuados.update([a for a in autores_recibidos if a])

    for a_id in autores_interactuados:
        if mi_autor and a_id == mi_autor.id:
            continue
        otro_autor = Autor.objects.filter(id=a_id).first()
        if not otro_autor:
            continue

        q_filter = (Q(remitente=request.user) & Q(destinatario=otro_autor))
        if otro_autor.usuario and mi_autor:
            q_filter |= (Q(remitente=otro_autor.usuario) & Q(destinatario=mi_autor))

        mensajes_hilo = MensajeInterno.objects.filter(
            es_soporte=False
        ).filter(q_filter).order_by('-fecha_envio')

        ult_msg = mensajes_hilo.first()

        no_leidos = 0
        if mi_autor and otro_autor.usuario:
            no_leidos = MensajeInterno.objects.filter(
                es_soporte=False,
                remitente=otro_autor.usuario,
                destinatario=mi_autor,
                leido=False
            ).count()

        conversaciones_directas.append({
            'contacto': otro_autor,
            'ultimo_mensaje': ult_msg,
            'no_leidos': no_leidos,
            'fecha_orden': ult_msg.fecha_envio if ult_msg else timezone.now()
        })

    conversaciones_directas.sort(key=lambda x: x['fecha_orden'], reverse=True)

    # =========================================================================
    # 2. SELECCIÓN DE LA CONVERSACIÓN ACTIVA
    # =========================================================================
    chat_activo = {
        'contacto': None,
        'mensajes': [],
        'titulo': '',
        'subtitulo': '',
    }

    if contacto_id:
        contacto = get_object_or_404(Autor, id=contacto_id)
        chat_activo['contacto'] = contacto
        chat_activo['titulo'] = contacto.nombre_con_titulo
        subt = contacto.institucion_origen or 'Docente FCA UABC'
        if contacto.codigo_institucional:
            subt += f" • ID: {contacto.codigo_institucional}"
        chat_activo['subtitulo'] = subt

        q_filter = (Q(remitente=request.user) & Q(destinatario=contacto))
        if contacto.usuario and mi_autor:
            q_filter |= (Q(remitente=contacto.usuario) & Q(destinatario=mi_autor))

        mensajes_directos = MensajeInterno.objects.filter(
            es_soporte=False
        ).filter(q_filter).order_by('fecha_envio')

        if mi_autor and contacto.usuario:
            MensajeInterno.objects.filter(
                es_soporte=False,
                remitente=contacto.usuario,
                destinatario=mi_autor,
                leido=False
            ).update(leido=True)

        chat_activo['mensajes'] = mensajes_directos

    elif conversaciones_directas:
        first_contacto = conversaciones_directas[0]['contacto']
        return redirect(f"{reverse('mensajeria')}?contacto={first_contacto.id}")

    # =========================================================================
    # 3. DIRECTORIO COMPLETO PARA EL MODAL "NUEVO MENSAJE"
    # =========================================================================
    # Solo mostrar autores con cuenta de usuario activa en el sistema para chatear
    autores_qs = Autor.objects.filter(
        usuario__isnull=False,
        usuario__is_active=True
    ).exclude(
        estado_cuenta__in=['suspendida', 'baja_voluntaria']
    ).order_by('nombre')
    if mi_autor:
        autores_qs = autores_qs.exclude(id=mi_autor.id)

    docentes_uabc = []
    docentes_externos = []
    investigadores = []

    for a in autores_qs:
        prefijo = a.obtener_prefijo_codigo_institucional()
        if prefijo == 'INV' or a.rol_facultad == 'INV_IND':
            investigadores.append(a)
        elif a.es_externo or (a.institucion_origen and a.institucion_origen.upper() != 'UABC'):
            docentes_externos.append(a)
        else:
            docentes_uabc.append(a)

    context = {
        'mi_autor': mi_autor,
        'conversaciones_directas': conversaciones_directas,
        'chat_activo': chat_activo,
        'docentes_uabc': docentes_uabc,
        'docentes_externos': docentes_externos,
        'investigadores': investigadores,
        'total_directos': len(conversaciones_directas),
    }
    return render(request, 'mensajeria.html', context)


@login_required
def soporte_institucional_view(request):
    """
    Mesa de Ayuda y Canal Dedicado de Soporte Institucional FCA.
    - Para docentes: Canal directo y confidencial con el equipo de Super Administradores.
    - Para superadministradores: Bandeja centralizada de atención y resolución de tickets.
    """
    mi_autor = getattr(request.user, 'autor', None)
    es_admin = request.user.is_superuser
    ticket_autor_id = request.GET.get('ticket_autor')
    filtro_estado = request.GET.get('estado')

    soporte_tickets_admin = []
    ticket_activo = {
        'usuario': None,
        'autor': None,
        'titulo': '',
        'subtitulo': '',
        'mensajes': [],
        'estado_soporte': 'abierto',
        'atendido_por': None,
    }

    if es_admin:
        # SUPERADMIN: Bandeja de tickets agrupados exclusivamente por docente cliente (no superadmins)
        remitentes_clientes_ids = set(
            MensajeInterno.objects.filter(es_soporte=True)
            .exclude(remitente__is_superuser=True)
            .order_by()
            .values_list('remitente_id', flat=True)
            .distinct()
        )

        destinatarios_autores_ids = set(
            MensajeInterno.objects.filter(es_soporte=True, destinatario__isnull=False)
            .order_by()
            .values_list('destinatario_id', flat=True)
            .distinct()
        )
        destinatarios_clientes_ids = set(
            User.objects.filter(autor__id__in=destinatarios_autores_ids, is_superuser=False)
            .values_list('id', flat=True)
        )

        clientes_ids = remitentes_clientes_ids.union(destinatarios_clientes_ids)

        todos_los_tickets = []
        conteo_abiertos = 0
        conteo_proceso = 0
        conteo_resueltos = 0

        for u_id in clientes_ids:
            u_obj = User.objects.filter(id=u_id, is_superuser=False).first()
            if not u_obj:
                continue
            t_autor = getattr(u_obj, 'autor', None)
            hilo_qs = MensajeInterno.objects.filter(es_soporte=True).filter(
                Q(remitente=u_obj) | (Q(destinatario=t_autor) if t_autor else Q())
            ).order_by('-fecha_envio')

            ult_msg = hilo_qs.first()

            no_leidos = MensajeInterno.objects.filter(
                es_soporte=True,
                remitente=u_obj,
                leido=False
            ).count()

            estado_actual = ult_msg.estado_soporte if ult_msg else 'abierto'

            if estado_actual == 'abierto':
                conteo_abiertos += 1
            elif estado_actual == 'en_proceso':
                conteo_proceso += 1
            elif estado_actual == 'resuelto':
                conteo_resueltos += 1

            ticket_data = {
                'usuario': u_obj,
                'autor': t_autor,
                'ultimo_mensaje': ult_msg,
                'no_leidos': no_leidos,
                'estado': estado_actual,
                'atendido_por': ult_msg.atendido_por if ult_msg else None,
                'fecha_orden': ult_msg.fecha_envio if ult_msg else timezone.now()
            }
            todos_los_tickets.append(ticket_data)

            if not filtro_estado or filtro_estado == 'todos' or estado_actual == filtro_estado:
                soporte_tickets_admin.append(ticket_data)

        soporte_tickets_admin.sort(key=lambda x: x['fecha_orden'], reverse=True)
        todos_los_tickets.sort(key=lambda x: x['fecha_orden'], reverse=True)

        target_user = None
        if ticket_autor_id:
            # Buscar por autor_id o user_id asegurando que sea un cliente docente
            target_user = User.objects.filter(autor__id=ticket_autor_id, is_superuser=False).first() or \
                          User.objects.filter(id=ticket_autor_id, is_superuser=False).first()

        # Si no se pasó ticket_autor_id o era un admin no válido, seleccionar el primer ticket disponible del filtro actual
        if not target_user and soporte_tickets_admin:
            target_user = soporte_tickets_admin[0]['usuario']
        elif not target_user and todos_los_tickets and (not filtro_estado or filtro_estado == 'todos'):
            target_user = todos_los_tickets[0]['usuario']

        if target_user:
            ticket_activo['usuario'] = target_user
            t_autor = getattr(target_user, 'autor', None)
            ticket_activo['autor'] = t_autor
            nombre_docente = t_autor.nombre_con_titulo if t_autor else (target_user.get_full_name() or target_user.username)
            ticket_activo['titulo'] = nombre_docente
            ticket_activo['subtitulo'] = f"{target_user.email or target_user.username} • {t_autor.institucion_origen if t_autor else 'UABC FCA'}"

            mensajes_soporte = MensajeInterno.objects.filter(
                es_soporte=True
            ).filter(
                Q(remitente=target_user) | (Q(destinatario=t_autor) if t_autor else Q())
            ).order_by('fecha_envio')

            MensajeInterno.objects.filter(
                es_soporte=True,
                remitente=target_user,
                leido=False
            ).update(leido=True)

            ticket_activo['mensajes'] = mensajes_soporte
            ult = mensajes_soporte.last()
            if ult:
                ticket_activo['estado_soporte'] = ult.estado_soporte
                ticket_activo['atendido_por'] = ult.atendido_por
        else:
            nombre_filtro = 'todos' if not filtro_estado or filtro_estado == 'todos' else filtro_estado.replace('_', ' ')
            ticket_activo['titulo'] = "Cola de Soporte FCA"
            ticket_activo['subtitulo'] = f"No hay solicitudes de soporte con estado '{nombre_filtro}' actualmente."
    else:
        # DOCENTE REGULAR: Su propio canal de soporte con la administración
        ticket_activo['titulo'] = "Mesa de Ayuda & Soporte Institucional"
        ticket_activo['subtitulo'] = "Canal directo con el equipo de Super Administradores FCA UABC"

        mensajes_soporte = MensajeInterno.objects.filter(
            es_soporte=True
        ).filter(
            Q(remitente=request.user) | (Q(destinatario=mi_autor) if mi_autor else Q())
        ).order_by('fecha_envio')

        if mi_autor:
            MensajeInterno.objects.filter(
                es_soporte=True,
                destinatario=mi_autor,
                leido=False
            ).update(leido=True)

        ticket_activo['mensajes'] = mensajes_soporte
        ult = mensajes_soporte.last()
        if ult:
            ticket_activo['estado_soporte'] = ult.estado_soporte
            ticket_activo['atendido_por'] = ult.atendido_por

    context = {
        'mi_autor': mi_autor,
        'es_admin': es_admin,
        'soporte_tickets_admin': soporte_tickets_admin,
        'ticket_activo': ticket_activo,
        'filtro_estado': filtro_estado or 'todos',
        'total_tickets': len(todos_los_tickets) if es_admin else 0,
        'conteo_abiertos': conteo_abiertos if es_admin else 0,
        'conteo_proceso': conteo_proceso if es_admin else 0,
        'conteo_resueltos': conteo_resueltos if es_admin else 0,
    }
    return render(request, 'soporte.html', context)


@login_required
def enviar_mensaje_interno_view(request):
    """
    Envía un mensaje institucional con soporte para texto, emojis y archivos adjuntos
    (PDF, Word, Excel, PowerPoint, imágenes). Admite respuesta AJAX o redirect estándar.
    """
    if request.method == 'POST':
        destinatario_id = request.POST.get('destinatario_id')
        es_soporte = request.POST.get('es_soporte') in ['1', 'true', 'True']
        ticket_autor_id = request.POST.get('ticket_autor_id')
        asunto = request.POST.get('asunto', '').strip()
        cuerpo = request.POST.get('cuerpo', '').strip()
        adjunto = request.FILES.get('adjunto')
        es_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1'

        if not cuerpo and not adjunto:
            if es_ajax:
                return JsonResponse({'success': False, 'error': 'Escribe un mensaje o adjunta un archivo.'}, status=400)
            messages.error(request, 'Debes escribir un mensaje o adjuntar un archivo.')
            return redirect('soporte_institucional' if es_soporte else 'mensajeria')

        nombre_adjunto = adjunto.name if adjunto else None

        # CASO 1: SOPORTE INSTITUCIONAL
        if es_soporte:
            # Superadmin respondiendo a un ticket docente
            if request.user.is_superuser and ticket_autor_id:
                destinatario_autor = Autor.objects.filter(id=ticket_autor_id).first()
                if not destinatario_autor:
                    u_target = User.objects.filter(id=ticket_autor_id).first()
                    destinatario_autor = getattr(u_target, 'autor', None) if u_target else None

                nuevo_msg = MensajeInterno.objects.create(
                    remitente=request.user,
                    destinatario=destinatario_autor,
                    es_soporte=True,
                    atendido_por=request.user,
                    estado_soporte='en_proceso',
                    asunto=asunto or "Respuesta de Soporte Institucional FCA",
                    cuerpo=cuerpo or "(Archivo adjunto)",
                    adjunto=adjunto,
                    nombre_adjunto=nombre_adjunto
                )

                if destinatario_autor and destinatario_autor.usuario:
                    MensajeInterno.objects.filter(
                        es_soporte=True,
                        remitente=destinatario_autor.usuario
                    ).update(atendido_por=request.user, estado_soporte='en_proceso')

                if es_ajax:
                    return JsonResponse({
                        'success': True,
                        'mensaje': {
                            'id': nuevo_msg.id,
                            'cuerpo': nuevo_msg.cuerpo,
                            'fecha': timezone.localtime(nuevo_msg.fecha_envio).strftime("%H:%M"),
                            'remitente': 'Soporte Institucional',
                            'remitente_nombre': 'Soporte Institucional',
                            'es_propio': True,
                            'adjunto_url': nuevo_msg.adjunto.url if nuevo_msg.adjunto else None,
                            'adjunto_nombre': nuevo_msg.nombre_adjunto,
                            'extension': nuevo_msg.extension_adjunto,
                            'es_imagen': nuevo_msg.es_imagen,
                            'es_pdf': nuevo_msg.es_pdf,
                            'es_documento': nuevo_msg.es_documento,
                            'es_presentacion': nuevo_msg.es_presentacion,
                            'es_hoja_calculo': nuevo_msg.es_hoja_calculo,
                        }
                    })
                messages.success(request, f'Respuesta enviada al ticket de {destinatario_autor.nombre if destinatario_autor else "docente"}.')
                return redirect(f"{reverse('soporte_institucional')}?ticket_autor={ticket_autor_id}")

            # Docente enviando consulta a Soporte
            nuevo_msg = MensajeInterno.objects.create(
                remitente=request.user,
                destinatario=None,
                es_soporte=True,
                estado_soporte='abierto',
                asunto=asunto or "Consulta a Soporte Institucional",
                cuerpo=cuerpo or "(Archivo adjunto)",
                adjunto=adjunto,
                nombre_adjunto=nombre_adjunto
            )

            if es_ajax:
                return JsonResponse({
                    'success': True,
                    'mensaje': {
                        'id': nuevo_msg.id,
                        'cuerpo': nuevo_msg.cuerpo,
                        'fecha': timezone.localtime(nuevo_msg.fecha_envio).strftime("%H:%M"),
                        'remitente': request.user.get_full_name() or request.user.username,
                        'remitente_nombre': request.user.get_full_name() or request.user.username,
                        'es_propio': True,
                        'adjunto_url': nuevo_msg.adjunto.url if nuevo_msg.adjunto else None,
                        'adjunto_nombre': nuevo_msg.nombre_adjunto,
                        'extension': nuevo_msg.extension_adjunto,
                        'es_imagen': nuevo_msg.es_imagen,
                        'es_pdf': nuevo_msg.es_pdf,
                        'es_documento': nuevo_msg.es_documento,
                        'es_presentacion': nuevo_msg.es_presentacion,
                        'es_hoja_calculo': nuevo_msg.es_hoja_calculo,
                    }
                })
            messages.success(request, 'Tu consulta ha sido enviada a Soporte Institucional. Un administrador te responderá a la brevedad.')
            return redirect('soporte_institucional')

        # CASO 2: MENSAJE DIRECTO ENTRE DOCENTES
        if not destinatario_id:
            if es_ajax:
                return JsonResponse({'success': False, 'error': 'Debes seleccionar un destinatario.'}, status=400)
            messages.error(request, 'Debes seleccionar un destinatario.')
            return redirect('mensajeria')

        destinatario = get_object_or_404(Autor, id=destinatario_id)
        if hasattr(request.user, 'autor') and destinatario == request.user.autor:
            if es_ajax:
                return JsonResponse({'success': False, 'error': 'No puedes enviarte un mensaje a ti mismo.'}, status=400)
            messages.error(request, 'No puedes enviarte un mensaje a ti mismo.')
            return redirect('mensajeria')

        nuevo_msg = MensajeInterno.objects.create(
            remitente=request.user,
            destinatario=destinatario,
            es_soporte=False,
            asunto=asunto or "Mensaje académico",
            cuerpo=cuerpo or "(Archivo adjunto)",
            adjunto=adjunto,
            nombre_adjunto=nombre_adjunto
        )

        try:
            notificar_nuevo_mensaje_interno(nuevo_msg)
        except Exception as e:
            logger.warning(f"Error al enviar correo de notificación de mensaje: {e}")

        if es_ajax:
            return JsonResponse({
                'success': True,
                'mensaje': {
                    'id': nuevo_msg.id,
                    'cuerpo': nuevo_msg.cuerpo,
                    'fecha': timezone.localtime(nuevo_msg.fecha_envio).strftime("%H:%M"),
                    'remitente': request.user.get_full_name() or request.user.username,
                    'es_propio': True,
                    'adjunto_url': nuevo_msg.adjunto.url if nuevo_msg.adjunto else None,
                    'adjunto_nombre': nuevo_msg.nombre_adjunto,
                    'extension': nuevo_msg.extension_adjunto,
                }
            })

        next_param = request.POST.get('next')
        if next_param:
            messages.success(request, f'Mensaje enviado con éxito a {destinatario.nombre}.')
            return redirect(next_param)
        return redirect(f"{reverse('mensajeria')}?contacto={destinatario.id}")

    return redirect('mensajeria')


@login_required
def marcar_mensaje_leido_view(request, mensaje_id):
    """Marca un mensaje académico como leído mediante AJAX."""
    mensaje = get_object_or_404(MensajeInterno, id=mensaje_id)
    if hasattr(request.user, 'autor') and mensaje.destinatario == request.user.autor:
        mensaje.leido = True
        mensaje.save()
        return JsonResponse({'success': True})
    elif request.user.is_superuser and mensaje.es_soporte:
        mensaje.leido = True
        mensaje.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)


@login_required
def obtener_mensajes_nuevos_ajax_view(request):
    """
    Endpoint reactivo para mensajería y tickets de soporte.
    Permite obtener mensajes nuevos en tiempo real sin tener que recargar la página.
    """
    mi_autor = getattr(request.user, 'autor', None)
    contacto_id = request.GET.get('contacto_id') or request.GET.get('contacto')
    es_soporte = request.GET.get('es_soporte') in ['1', 'true', 'True']
    ticket_autor_id = request.GET.get('ticket_autor_id')
    ultimo_id = request.GET.get('ultimo_id', 0)
    try:
        ultimo_id = int(ultimo_id)
    except (ValueError, TypeError):
        ultimo_id = 0

    mensajes_nuevos = []

    if es_soporte:
        if request.user.is_superuser and ticket_autor_id:
            # Superadmin consultando ticket de un docente
            target_autor = Autor.objects.filter(id=ticket_autor_id).first()
            target_user = target_autor.usuario if target_autor else None
            if not target_user:
                target_user = User.objects.filter(id=ticket_autor_id, is_superuser=False).first()
                if target_user:
                    target_autor = getattr(target_user, 'autor', None)

            if target_user or target_autor:
                q_soporte = (
                    (Q(remitente=target_user) if target_user else Q()) |
                    (Q(destinatario=target_autor) if target_autor else Q())
                )
                qs = MensajeInterno.objects.filter(
                    es_soporte=True,
                    id__gt=ultimo_id
                ).filter(q_soporte).order_by('fecha_envio')

                # Marcar como leídos los que envió el usuario cliente
                if target_user:
                    MensajeInterno.objects.filter(
                        es_soporte=True,
                        remitente=target_user,
                        leido=False
                    ).update(leido=True)
                mensajes_nuevos = list(qs)
        else:
            # Docente consultando su ticket de soporte
            qs = MensajeInterno.objects.filter(
                es_soporte=True,
                id__gt=ultimo_id
            ).filter(
                Q(remitente=request.user) | (Q(destinatario=mi_autor) if mi_autor else Q())
            ).order_by('fecha_envio')

            # Marcar como leídos los que le enviaron al docente
            if mi_autor:
                MensajeInterno.objects.filter(
                    es_soporte=True,
                    destinatario=mi_autor,
                    leido=False
                ).update(leido=True)
            mensajes_nuevos = list(qs)
    elif contacto_id:
        contacto = Autor.objects.filter(id=contacto_id).first()
        if contacto:
            q_filter = (Q(remitente=request.user) & Q(destinatario=contacto))
            if contacto.usuario and mi_autor:
                q_filter |= (Q(remitente=contacto.usuario) & Q(destinatario=mi_autor))

            qs = MensajeInterno.objects.filter(
                es_soporte=False,
                id__gt=ultimo_id
            ).filter(q_filter).order_by('fecha_envio')

            if mi_autor and contacto.usuario:
                MensajeInterno.objects.filter(
                    es_soporte=False,
                    remitente=contacto.usuario,
                    destinatario=mi_autor,
                    leido=False
                ).update(leido=True)
            mensajes_nuevos = list(qs)

    data = []
    for m in mensajes_nuevos:
        es_propio = (m.remitente == request.user)
        nombre_remitente = "Tú" if es_propio else (
            "Soporte Institucional" if (m.es_soporte and m.remitente.is_superuser) else (
                m.remitente.get_full_name() or m.remitente.username
            )
        )
        data.append({
            'id': m.id,
            'cuerpo': m.cuerpo,
            'fecha': timezone.localtime(m.fecha_envio).strftime("%H:%M"),
            'es_propio': es_propio,
            'remitente_nombre': nombre_remitente,
            'adjunto_url': m.adjunto.url if m.adjunto else None,
            'adjunto_nombre': m.nombre_adjunto or (m.adjunto.name.split('/')[-1] if m.adjunto else None),
            'es_imagen': m.es_imagen,
            'es_pdf': m.es_pdf,
            'es_documento': m.es_documento,
            'es_presentacion': m.es_presentacion,
            'es_hoja_calculo': m.es_hoja_calculo,
            'extension': m.extension_adjunto,
            'leido': m.leido,
        })

    # Conteo global de no leídos para badges
    no_leidos_global = 0
    if mi_autor:
        no_leidos_global = MensajeInterno.objects.filter(destinatario=mi_autor, leido=False).count()

    return JsonResponse({
        'success': True,
        'mensajes': data,
        'no_leidos_global': no_leidos_global
    })


@login_required
@user_passes_test(es_superusuario, login_url='/login/')
def cambiar_estado_soporte_view(request, ticket_autor_id):
    """Permite al superadministrador cambiar el estado del ticket de soporte (resuelto, abierto, en_proceso)."""
    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado', 'resuelto').strip().lower()
        if nuevo_estado not in ['abierto', 'en_proceso', 'resuelto']:
            nuevo_estado = 'en_proceso'

        target_autor = Autor.objects.filter(id=ticket_autor_id).first()
        target_user = None
        if target_autor:
            target_user = target_autor.usuario
        if not target_user:
            target_user = User.objects.filter(id=ticket_autor_id, is_superuser=False).first()
            if target_user:
                target_autor = getattr(target_user, 'autor', None)

        if target_user or target_autor:
            q_hilo = Q()
            if target_user:
                q_hilo |= Q(remitente=target_user)
            if target_autor:
                q_hilo |= Q(destinatario=target_autor)

            MensajeInterno.objects.filter(
                es_soporte=True
            ).filter(q_hilo).update(estado_soporte=nuevo_estado, atendido_por=request.user)

            messages.success(request, f'Estado del ticket actualizado a: {nuevo_estado.upper().replace("_", " ")}.')

        target_param = target_autor.id if target_autor else (target_user.id if target_user else ticket_autor_id)
        return redirect(f"{reverse('soporte_institucional')}?ticket_autor={target_param}")
    return redirect('soporte_institucional')


@user_passes_test(es_superusuario, login_url='/login/')
def fusionar_autores_view(request):
    """Permite al SuperAdmin unificar uno o más autores duplicados en un único autor canónico."""
    if request.method == 'POST':
        autor_principal_id = request.POST.get('autor_principal_id')
        duplicados_ids = request.POST.getlist('autores_duplicados_ids')

        if not autor_principal_id or not duplicados_ids:
            messages.error(request, 'Debes seleccionar el autor principal canónico y al menos un autor duplicado para fusionar.')
            return redirect(f"{reverse('panel_usuarios')}#autores-fusion")

        autor_principal = get_object_or_404(Autor, id=autor_principal_id)
        duplicados = Autor.objects.filter(id__in=duplicados_ids).exclude(id=autor_principal.id)

        if not duplicados.exists():
            messages.warning(request, 'No se encontraron autores duplicados válidos para fusionar.')
            return redirect(f"{reverse('panel_usuarios')}#autores-fusion")

        total_docs_transferidos = 0
        total_asesorias_transferidas = 0
        nombres_fusionados = []
        snapshot_duplicados = []

        for dup in duplicados:
            nombres_fusionados.append(f"{dup.nombre} ({dup.codigo_institucional or 'Sin ID'})")

            # Snapshot de relaciones antes de transferir
            art_ids = list(dup.documentos.values_list('id', flat=True))
            arts_donde_principal_ya_era_autor = list(
                Articulo.objects.filter(id__in=art_ids, autor=autor_principal).values_list('id', flat=True)
            )
            asesorias_ids = list(Articulo.objects.filter(asesor=dup).values_list('id', flat=True))
            coasesorias_ids = list(Articulo.objects.filter(coasesor=dup).values_list('id', flat=True))
            invitaciones_ids = list(InvitacionCoautoria.objects.filter(autor_invitado=dup).values_list('id', flat=True))
            mensajes_ids = list(MensajeInterno.objects.filter(destinatario=dup).values_list('id', flat=True))

            dup_info = {
                'id': dup.id,
                'nombre': dup.nombre,
                'titulo_academico': dup.titulo_academico,
                'nombres': dup.nombres,
                'apellido_paterno': dup.apellido_paterno,
                'apellido_materno': dup.apellido_materno,
                'codigo_institucional': dup.codigo_institucional,
                'orcid': dup.orcid,
                'institucion_origen': dup.institucion_origen,
                'correo': dup.correo,
                'es_profesor': dup.es_profesor,
                'es_externo': dup.es_externo,
                'biografia': dup.biografia,
                'usuario_id': dup.usuario_id,
                'era_usuario_activo': bool(dup.usuario),
                'articulos_ids': art_ids,
                'arts_donde_principal_ya_era_autor': arts_donde_principal_ya_era_autor,
                'asesorias_ids': asesorias_ids,
                'coasesorias_ids': coasesorias_ids,
                'invitaciones_ids': invitaciones_ids,
                'mensajes_ids': mensajes_ids,
            }
            snapshot_duplicados.append(dup_info)

            # 1. Transferir autorías en artículos (ManyToMany)
            for art in dup.documentos.all():
                art.autor.add(autor_principal)
                art.autor.remove(dup)
                total_docs_transferidos += 1

            # 2. Transferir asesorías y coasesorías de tesis (ForeignKey)
            asesorias = Articulo.objects.filter(asesor=dup)
            total_asesorias_transferidas += asesorias.count()
            asesorias.update(asesor=autor_principal)

            coasesorias = Articulo.objects.filter(coasesor=dup)
            total_asesorias_transferidas += coasesorias.count()
            coasesorias.update(coasesor=autor_principal)

            # 3. Transferir invitaciones y mensajes
            InvitacionCoautoria.objects.filter(autor_invitado=dup).update(autor_invitado=autor_principal)
            MensajeInterno.objects.filter(destinatario=dup).update(destinatario=autor_principal)

            # 4. Eliminar el registro duplicado si no tiene cuenta de usuario vinculada
            if not dup.usuario:
                dup.delete()
            else:
                dup.biografia = f"[Perfil fusionado en {autor_principal.nombre}] {dup.biografia or ''}".strip()
                dup.save()

        # 5. Registrar en HistorialFusion para permitir auditoría y reversión completa
        HistorialFusion.objects.create(
            admin_usuario=request.user,
            autor_principal=autor_principal,
            nombre_principal_snapshot=autor_principal.nombre,
            codigo_principal_snapshot=autor_principal.codigo_institucional,
            datos_duplicados_json=json.dumps(snapshot_duplicados),
            total_obras_transferidas=total_docs_transferidos,
            total_asesorias_transferidas=total_asesorias_transferidas,
        )

        detalle_audit = (
            f"Fusionó a: {', '.join(nombres_fusionados)} dentro del autor canónico: "
            f"{autor_principal.nombre} [{autor_principal.codigo_institucional}]. "
            f"Obras transferidas: {total_docs_transferidos}, Asesorías transferidas: {total_asesorias_transferidas}."
        )
        registrar_auditoria(request.user, "Fusión y Deduplicación de Autores", detalle_audit)
        messages.success(request, f'Fusión completada con éxito. Se unificaron {len(nombres_fusionados)} registro(s) en "{autor_principal.nombre}" [{autor_principal.codigo_institucional}]. Puedes consultarla y revertirla si lo requieres en "Fusiones del Día".')
        return redirect(f"{reverse('panel_usuarios')}#autores-fusion")

    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def revertir_fusion_view(request, fusion_id):
    """
    Permite al SuperAdmin revertir (deshacer) una fusión previa:
    Restaura los perfiles de autores absorbidos y les devuelve sus obras, asesorías y coautorías.
    """
    if request.method == 'POST':
        fusion = get_object_or_404(HistorialFusion, id=fusion_id)
        if fusion.revertida:
            messages.warning(request, 'Esta fusión ya ha sido revertida anteriormente.')
            return redirect(f"{reverse('panel_usuarios')}#autores-fusion")

        autor_principal = fusion.autor_principal
        duplicados_data = fusion.get_duplicados_list()
        total_obras_restauradas = 0
        total_asesorias_restauradas = 0
        nombres_restaurados = []

        for d in duplicados_data:
            dup_id = d.get('id')
            nombre = d.get('nombre', 'Autor Restaurado')
            nombres_restaurados.append(nombre)

            # 1. Recuperar o recrear el autor duplicado
            dup = Autor.objects.filter(id=dup_id).first()
            if not dup:
                cod = d.get('codigo_institucional')
                if cod and Autor.objects.filter(codigo_institucional=cod).exists():
                    cod = None

                dup = Autor(
                    id=dup_id,
                    nombre=nombre,
                    titulo_academico=d.get('titulo_academico'),
                    nombres=d.get('nombres'),
                    apellido_paterno=d.get('apellido_paterno'),
                    apellido_materno=d.get('apellido_materno'),
                    codigo_institucional=cod,
                    orcid=d.get('orcid'),
                    institucion_origen=d.get('institucion_origen', 'UABC'),
                    correo=d.get('correo'),
                    es_profesor=d.get('es_profesor', False),
                    es_externo=d.get('es_externo', False),
                    biografia=d.get('biografia', ''),
                    usuario_id=d.get('usuario_id'),
                )
                dup.save(force_insert=True)
            else:
                dup.biografia = d.get('biografia', '')
                dup.save()

            # 2. Restaurar autorías en artículos
            arts_donde_principal_ya_era_autor = d.get('arts_donde_principal_ya_era_autor', [])
            for art_id in d.get('articulos_ids', []):
                art = Articulo.objects.filter(id=art_id).first()
                if art:
                    art.autor.add(dup)
                    if art_id not in arts_donde_principal_ya_era_autor:
                        art.autor.remove(autor_principal)
                    total_obras_restauradas += 1

            # 3. Restaurar asesorías y coasesorías
            for asesoria_id in d.get('asesorias_ids', []):
                Articulo.objects.filter(id=asesoria_id).update(asesor=dup)
                total_asesorias_restauradas += 1

            for coasesoria_id in d.get('coasesorias_ids', []):
                Articulo.objects.filter(id=coasesoria_id).update(coasesor=dup)
                total_asesorias_restauradas += 1

            # 4. Restaurar invitaciones y mensajes
            for inv_id in d.get('invitaciones_ids', []):
                InvitacionCoautoria.objects.filter(id=inv_id).update(autor_invitado=dup)

            for msg_id in d.get('mensajes_ids', []):
                MensajeInterno.objects.filter(id=msg_id).update(destinatario=dup)

        # 5. Marcar la fusión como revertida
        fusion.revertida = True
        fusion.fecha_reversion = timezone.now()
        fusion.revertida_por = request.user
        fusion.save()

        # Auditoría
        detalle = (
            f"Revirtió la fusión de: {', '.join(nombres_restaurados)} separándolo de "
            f"{fusion.nombre_principal_snapshot}. Obras restauradas: {total_obras_restauradas}, "
            f"Asesorías restauradas: {total_asesorias_restauradas}."
        )
        registrar_auditoria(request.user, "Reversión de Fusión de Autores", detalle)

        messages.success(
            request,
            f'¡Fusión revertida con éxito! Se restauró el perfil de {", ".join(nombres_restaurados)} '
            f'y se le devolvieron sus {total_obras_restauradas} obra(s) y {total_asesorias_restauradas} asesoría(s).'
        )
        return redirect(f"{reverse('panel_usuarios')}#autores-fusion")

    return redirect('panel_usuarios')


@login_required
@user_passes_test(es_superusuario, login_url='/login/')
def limpiar_autores_huerfanos_admin_view(request):
    """Permite al SuperAdmin depurar autores huérfanos con o sin período de gracia de 15 minutos."""
    modo = request.GET.get('modo', request.POST.get('modo', 'seguros'))
    if modo in ['todos', 'forzar']:
        total = limpiar_autores_huerfanos(minutos_gracia=0)
        criterio_str = "todos los huérfanos sin período de gracia"
    else:
        total = limpiar_autores_huerfanos(minutos_gracia=15)
        criterio_str = "huérfanos inactivos con más de 15 minutos de antigüedad (período de gracia respetado)"

    registrar_auditoria(request.user, "Depuración de Catálogo", f"Purgó {total} autores huérfanos ({criterio_str}).")
    if total > 0:
        messages.success(request, f'¡Limpieza exitosa! Se eliminaron {total} autor(es) huérfano(s) ({criterio_str}).')
    else:
        messages.info(request, f'El catálogo está limpio. No se encontraron autores huérfanos para depurar ({criterio_str}).')
    return redirect(f"{reverse('panel_usuarios')}#autores-fusion")


@login_required
@user_passes_test(es_superusuario, login_url='/login/')
def eliminar_autor_huerfano_individual_view(request, autor_id):
    """Permite al SuperAdmin eliminar un autor específico que no tiene cuenta ni obras."""
    target_autor = get_object_or_404(Autor, id=autor_id)

    if target_autor.usuario:
        messages.error(request, f'No se puede eliminar a "{target_autor.nombre}" porque tiene una cuenta de usuario vinculada ({target_autor.usuario.username}).')
        return redirect(f"{reverse('panel_usuarios')}#autores-fusion")

    if target_autor.documentos.exists() or target_autor.tesis_asesoradas.exists() or target_autor.tesis_coasesoradas.exists():
        messages.error(request, f'No se puede eliminar a "{target_autor.nombre}" porque tiene publicaciones o asesorías asociadas. Debes desvincularlo primero o usar la Herramienta de Fusión.')
        return redirect(f"{reverse('panel_usuarios')}#autores-fusion")

    nombre_autor = target_autor.nombre
    target_autor.delete()
    registrar_auditoria(request.user, "Eliminación Manual de Autor", f"Eliminó manualmente al autor huérfano: {nombre_autor}")
    messages.success(request, f'El autor huérfano "{nombre_autor}" ha sido eliminado exitosamente del catálogo.')
    return redirect(f"{reverse('panel_usuarios')}#autores-fusion")



@login_required
def cambiar_password_propia_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            try:
                notificar_alerta_cambio_password(user)
            except Exception as e:
                logger.warning(f"Error al enviar correo de alerta de cambio de password: {e}")
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

    if autor.biografia_borrador is not None:
        autor.biografia = autor.biografia_borrador
    if autor.biografia_extendida_borrador is not None:
        autor.biografia_extendida = autor.biografia_extendida_borrador
    if autor.foto_perfil_borrador:
        autor.foto_perfil = autor.foto_perfil_borrador
    if autor.reconocimiento_pdf_borrador:
        autor.reconocimiento_pdf = autor.reconocimiento_pdf_borrador
    if autor.horario_pdf_borrador:
        autor.horario_pdf = autor.horario_pdf_borrador

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
        autor.rol_facultad = cargos_seleccionados[0] if cargos_seleccionados else 'OTRO'

        # Guardamos el texto en los campos oficiales Y en los borradores
        autor.biografia = biografia
        autor.biografia_borrador = biografia
        autor.biografia_extendida = biografia_extendida
        autor.biografia_extendida_borrador = biografia_extendida

        # Aprobamos la semblanza automáticamente al editar
        autor.estado_semblanza = 'aprobado'
        autor.perfil_completado = True
        autor.motivo_rechazo_semblanza = ''
        autor.moderado_por_semblanza = request.user

        autor.save()

        autor.nombramientos.all().delete()
        cargo_personalizado_val = request.POST.get('cargo_personalizado', '').strip()
        for rol_codigo in cargos_seleccionados:
            if rol_codigo == 'CUSTOM':
                if cargo_personalizado_val:
                    Nombramiento.objects.create(autor=autor, rol='CUSTOM', cargo_personalizado=cargo_personalizado_val)
            else:
                Nombramiento.objects.create(autor=autor, rol=rol_codigo)

        autor.enlaces_profesionales.all().delete()
        plataformas = request.POST.getlist('enlace_plataforma[]')
        urls = request.POST.getlist('enlace_url[]')
        emojis = request.POST.getlist('enlace_emoji[]')

        for plat, u, em in zip(plataformas, urls, emojis):
            p_text = plat.strip()
            u_text = u.strip()
            if p_text and u_text:
                if not u_text.startswith(('http://', 'https://')):
                    u_text = 'https://' + u_text
                em_text = em.strip()[:20] if em.strip() else '🔗'
                EnlaceProfesional.objects.create(
                    autor=autor,
                    plataforma=p_text,
                    url=u_text,
                    emoji=em_text
                )

        registrar_auditoria(request.user, "Edición de Ficha Académica",
                            f"Editó y aprobó la semblanza de: {autor.nombre}")
        messages.success(request, f'Ficha académica de "{autor.nombre}" actualizada y aprobada exitosamente.')

    return redirect('panel_usuarios')


# ==============================================================================
# DIRECTORIO PÚBLICO DEL CLAUSTRO Y RED DE UNIVERSIDADES
# ==============================================================================

def directorio_profesores_view(request):
    profesores_uabc_qs = Autor.objects.filter(
        usuario__isnull=False,
        es_profesor=True,
        estado_semblanza='aprobado',
        perfil_completado=True,
        institucion_origen__iexact='UABC'
    ).exclude(
        Q(rol_facultad='INV_IND') | Q(institucion_origen__icontains='independiente')
    ).prefetch_related(
        'documentos', 'nombramientos', 'enlaces_profesionales', 'mensajes_recibidos'
    ).order_by('nombre')

    profesores_externos_qs = Autor.objects.filter(
        usuario__isnull=False,
        es_profesor=True,
        estado_semblanza='aprobado',
        perfil_completado=True
    ).exclude(
        institucion_origen__iexact='UABC'
    ).exclude(
        Q(rol_facultad='INV_IND') | Q(institucion_origen__icontains='independiente')
    ).prefetch_related(
        'documentos', 'nombramientos', 'enlaces_profesionales', 'mensajes_recibidos'
    ).order_by('nombre')

    profesores_investigadores_qs = Autor.objects.filter(
        usuario__isnull=False,
        es_profesor=True,
        estado_semblanza='aprobado',
        perfil_completado=True
    ).filter(
        Q(rol_facultad='INV_IND') | Q(institucion_origen__icontains='independiente')
    ).prefetch_related(
        'documentos', 'nombramientos', 'enlaces_profesionales', 'mensajes_recibidos'
    ).order_by('nombre')

    # Priorización: Los profesores que cumplen años hoy aparecen al inicio
    profesores_uabc = sorted(list(profesores_uabc_qs), key=lambda p: (not p.es_cumpleanos_hoy, p.nombre))
    profesores_externos = sorted(list(profesores_externos_qs), key=lambda p: (not p.es_cumpleanos_hoy, p.nombre))
    profesores_investigadores = sorted(list(profesores_investigadores_qs), key=lambda p: (not p.es_cumpleanos_hoy, p.nombre))
    todos_profesores = sorted(
        profesores_uabc + profesores_externos + profesores_investigadores,
        key=lambda p: (not p.es_cumpleanos_hoy, p.nombre)
    )

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

    # Podio de Productividad (Top 3 Investigadores más prolíficos con obras aprobadas)
    podio_investigadores = sorted(
        [p for p in todos_profesores if p.total_obras_aprobadas > 0],
        key=lambda p: p.total_obras_aprobadas,
        reverse=True
    )[:3]

    context = {
        'profesores_uabc': profesores_uabc,
        'profesores_externos': profesores_externos,
        'profesores_investigadores': profesores_investigadores,
        'todos_profesores': todos_profesores,
        'podio_investigadores': podio_investigadores,
        'total_profesores': len(todos_profesores),
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


def normalizar_titulo_para_duplicados(texto):
    if not texto:
        return ""
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8').lower()
    texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
    return " ".join(texto.split())


def enriquecer_con_deteccion_duplicados(documentos):
    """Detecta posibles obras duplicadas por DOI idéntico, ISBN o títulos con alta similitud."""
    if not documentos:
        return

    todas_activas = list(Articulo.objects.filter(en_papelera=False).values(
        'id', 'titulo', 'doi_enlace', 'isbn_issn', 'estado', 'año_produccion'
    ))

    # Asegurar que documentos pasados también estén indexados para cotejo mutuo
    ids_existentes = {x['id'] for x in todas_activas}
    for d in documentos:
        doc_id = getattr(d, 'id', None)
        if doc_id and doc_id not in ids_existentes:
            todas_activas.append({
                'id': doc_id,
                'titulo': getattr(d, 'titulo', '') or '',
                'doi_enlace': getattr(d, 'doi_enlace', '') or '',
                'isbn_issn': getattr(d, 'isbn_issn', '') or '',
                'estado': getattr(d, 'estado', 'pendiente'),
                'año_produccion': getattr(d, 'año_produccion', None)
            })
            ids_existentes.add(doc_id)

    por_doi = {}
    por_isbn = {}
    por_titulo = {}

    for item in todas_activas:
        doi = (item['doi_enlace'] or '').strip().lower()
        if doi and len(doi) > 4:
            por_doi.setdefault(doi, []).append(item)

        isbn = re.sub(r'[^0-9xX]', '', (item['isbn_issn'] or '').lower())
        if isbn and len(isbn) >= 8:
            por_isbn.setdefault(isbn, []).append(item)

        norm_t = normalizar_titulo_para_duplicados(item['titulo'])
        if norm_t:
            por_titulo.setdefault(norm_t, []).append(item)

    for doc in documentos:
        doc.posible_duplicado = None
        doc_doi = (doc.doi_enlace or '').strip().lower()
        doc_isbn = re.sub(r'[^0-9xX]', '', (doc.isbn_issn or '').lower())
        doc_norm_t = normalizar_titulo_para_duplicados(doc.titulo)

        # 1. Coincidencia de DOI
        if doc_doi and len(doc_doi) > 4 and doc_doi in por_doi:
            otros = [x for x in por_doi[doc_doi] if x['id'] != doc.id]
            if otros:
                c = otros[0]
                doc.posible_duplicado = {
                    'id': c['id'],
                    'titulo': c['titulo'],
                    'motivo': 'Mismo DOI',
                    'estado': c['estado'],
                    'año': c['año_produccion']
                }
                continue

        # 2. Coincidencia de ISBN / ISSN
        if doc_isbn and len(doc_isbn) >= 8 and doc_isbn in por_isbn:
            otros = [x for x in por_isbn[doc_isbn] if x['id'] != doc.id]
            if otros:
                c = otros[0]
                doc.posible_duplicado = {
                    'id': c['id'],
                    'titulo': c['titulo'],
                    'motivo': 'Mismo ISBN/ISSN',
                    'estado': c['estado'],
                    'año': c['año_produccion']
                }
                continue

        # 3. Coincidencia exacta de título normalizado
        if doc_norm_t and doc_norm_t in por_titulo:
            otros = [x for x in por_titulo[doc_norm_t] if x['id'] != doc.id]
            if otros:
                c = otros[0]
                doc.posible_duplicado = {
                    'id': c['id'],
                    'titulo': c['titulo'],
                    'motivo': 'Título idéntico',
                    'estado': c['estado'],
                    'año': c['año_produccion']
                }
                continue

        # 4. Similitud difusa (>88%)
        if len(doc_norm_t) >= 15:
            mejor_ratio = 0
            mejor_match = None
            for item in todas_activas:
                if item['id'] == doc.id:
                    continue
                t_otro = normalizar_titulo_para_duplicados(item['titulo'])
                if abs(len(t_otro) - len(doc_norm_t)) <= 25:
                    ratio = SequenceMatcher(None, doc_norm_t, t_otro).ratio()
                    if ratio > 0.88 and ratio > mejor_ratio:
                        mejor_ratio = ratio
                        mejor_match = item
            if mejor_match:
                doc.posible_duplicado = {
                    'id': mejor_match['id'],
                    'titulo': mejor_match['titulo'],
                    'motivo': f'Título {int(mejor_ratio * 100)}% similar',
                    'estado': mejor_match['estado'],
                    'año': mejor_match['año_produccion']
                }


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

    q_docs = request.GET.get('q_docs', '').strip()
    q_semb = request.GET.get('q_semb', '').strip()
    q_autores = request.GET.get('q_autores', '').strip()

    # Documentos activos (excluyendo papelera de reciclaje)
    todos_documentos_qs = Articulo.objects.filter(en_papelera=False).order_by('-created_at')
    documentos_pendientes_qs = Articulo.objects.filter(estado='pendiente', en_papelera=False).order_by('-created_at')
    subidas_automaticas_qs = Articulo.objects.filter(es_subida_automatica=True, en_papelera=False).order_by('-created_at')

    # Obras en la Papelera de Reciclaje
    documentos_papelera_qs = Articulo.objects.filter(en_papelera=True).order_by('-fecha_eliminacion')
    total_papelera = documentos_papelera_qs.count()

    if q_docs:
        filtro_docs = (
            Q(titulo__icontains=q_docs) |
            Q(autor__nombre__icontains=q_docs) |
            Q(subido_por__username__icontains=q_docs) |
            Q(palabras_clave__icontains=q_docs) |
            Q(editorial__icontains=q_docs) |
            Q(revista__icontains=q_docs) |
            Q(doi_enlace__icontains=q_docs) |
            Q(isbn_issn__icontains=q_docs) |
            Q(area__nombre__icontains=q_docs) |
            Q(tipo_contenido__nombre__icontains=q_docs)
        )
        todos_documentos_qs = todos_documentos_qs.filter(filtro_docs).distinct()
        documentos_pendientes_qs = documentos_pendientes_qs.filter(filtro_docs).distinct()
        subidas_automaticas_qs = subidas_automaticas_qs.filter(filtro_docs).distinct()
        documentos_papelera_qs = documentos_papelera_qs.filter(filtro_docs).distinct()

    paginator_docs = Paginator(todos_documentos_qs, 20)
    page_docs = request.GET.get('page_docs')
    todos_documentos = paginator_docs.get_page(page_docs)

    # Detección inteligente de duplicados (Idea 3)
    enriquecer_con_deteccion_duplicados(todos_documentos.object_list)

    paginator_pendientes = Paginator(documentos_pendientes_qs, 20)
    page_pendientes = request.GET.get('page_pendientes')
    documentos_pendientes = paginator_pendientes.get_page(page_pendientes)
    enriquecer_con_deteccion_duplicados(documentos_pendientes.object_list)

    paginator_auto = Paginator(subidas_automaticas_qs, 20)
    page_auto = request.GET.get('page_auto')
    subidas_automaticas = paginator_auto.get_page(page_auto)
    enriquecer_con_deteccion_duplicados(subidas_automaticas.object_list)

    # Métricas de publicaciones de confianza (directas)
    subidas_auto_pendientes_chequeo = Articulo.objects.filter(es_subida_automatica=True, chequeado_por_moderador=False, en_papelera=False).count()
    subidas_auto_total = Articulo.objects.filter(es_subida_automatica=True, en_papelera=False).count()

    # Detección de usuarios candidatos a Confianza: Racha de 10+ obras consecutivas aprobadas sin rechazos ni correcciones
    # Si la obra más reciente o alguna en los últimos 10 envíos fue rechazada/devuelta, la racha se reinicia.
    ids_candidatos_confianza = set()
    rachas_aprobadas_por_usuario = {}
    usuarios_activos_con_obras = User.objects.filter(is_active=True, articulos_subidos__isnull=False).distinct()
    for usr in usuarios_activos_con_obras:
        # Obtener los estados de las publicaciones en orden cronológico inverso (de la más reciente a la más antigua)
        estados_obras = list(Articulo.objects.filter(subido_por=usr).order_by('-created_at').values_list('estado', flat=True))
        racha = 0
        for est in estados_obras:
            if est == 'aprobado':
                racha += 1
            else:
                # Cualquier rechazo, corrección o pendiente corta la racha consecutiva de aprobadas
                break
        rachas_aprobadas_por_usuario[usr.id] = racha
        if racha >= 10:
            ids_candidatos_confianza.add(usr.id)

    total_candidatos_sin_credencial = User.objects.filter(
        id__in=ids_candidatos_confianza,
        autor__is_trusted_publisher=False
    ).count()

    todas_semblanzas_qs = Autor.objects.filter(usuario__isnull=False, es_profesor=True).exclude(estado_semblanza='borrador').order_by('nombre')
    if q_semb:
        todas_semblanzas_qs = todas_semblanzas_qs.filter(
            Q(nombre__icontains=q_semb) |
            Q(codigo_institucional__icontains=q_semb) |
            Q(correo__icontains=q_semb) |
            Q(usuario__username__icontains=q_semb)
        ).distinct()

    paginator_semb = Paginator(todas_semblanzas_qs, 15)
    page_semb = request.GET.get('page_semb')
    todas_semblanzas = paginator_semb.get_page(page_semb)

    # Catálogo y herramienta de fusión de autores
    autores_catalogo_qs = Autor.objects.annotate(
        num_documentos=Count('documentos', distinct=True),
        num_asesorias=Count('tesis_asesoradas', distinct=True) + Count('tesis_coasesoradas', distinct=True)
    ).order_by('nombre')

    if q_autores:
        autores_catalogo_qs = autores_catalogo_qs.filter(
            Q(nombre__icontains=q_autores) |
            Q(codigo_institucional__icontains=q_autores) |
            Q(orcid__icontains=q_autores) |
            Q(institucion_origen__icontains=q_autores) |
            Q(usuario__username__icontains=q_autores)
        ).distinct()

    paginator_autores = Paginator(autores_catalogo_qs, 20)
    page_autores = request.GET.get('page_autores')
    autores_catalogo = paginator_autores.get_page(page_autores)

    # Solicitudes pendientes de registro (tanto autenticadas como pendientes de código OTP)
    pendientes = User.objects.filter(
        is_active=False
    ).filter(
        Q(autor__estado_cuenta__in=['pendiente', 'pendiente_verificacion']) | Q(autor__isnull=True)
    ).order_by('-date_joined')

    # Cuentas suspendidas o dadas de baja por el usuario
    suspendidas = User.objects.filter(
        autor__estado_cuenta__in=['suspendida', 'baja_voluntaria']
    ).order_by('-autor__fecha_suspension')

    # Administrativos y Docentes activos
    administrativos = User.objects.filter(
        is_superuser=False,
        is_staff=True,
        is_active=True
    ).filter(
        Q(autor__estado_cuenta='activa') | Q(autor__isnull=True)
    ).order_by('username')

    # Superusuarios activos
    superusuarios = User.objects.filter(
        is_superuser=True,
        is_active=True
    ).order_by('username')

    # Autores huérfanos para diagnóstico y modal de limpieza
    limite_15m = timezone.now() - timedelta(minutes=15)
    qs_huerfanos = Autor.objects.filter(
        usuario__isnull=True,
        documentos__isnull=True,
        tesis_asesoradas__isnull=True,
        tesis_coasesoradas__isnull=True,
        invitaciones_recibidas__isnull=True
    ).order_by('-created_at')

    total_huerfanos = qs_huerfanos.count()
    total_huerfanos_inactivos = qs_huerfanos.filter(Q(created_at__lte=limite_15m) | Q(created_at__isnull=True)).count()
    total_huerfanos_recientes = qs_huerfanos.filter(created_at__gt=limite_15m).count()
    lista_huerfanos = list(qs_huerfanos[:40])

    # Detección inteligente de duplicados / parecidos
    grupos_parecidos = detectar_grupos_autores_parecidos(Autor.objects.all())

    # Fusiones de autores e historial de reversión
    hoy_inicio = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    total_fusiones_hoy = HistorialFusion.objects.filter(fecha_fusion__gte=hoy_inicio, revertida=False).count()
    fusiones_recientes = HistorialFusion.objects.select_related('admin_usuario', 'revertida_por', 'autor_principal').all().order_by('-fecha_fusion')[:40]

    # ========================================================
    # ESTADÍSTICAS Y ANALÍTICA DE PRODUCCIÓN (BLOQUE 3)
    # ========================================================
    anio_actual = timezone.now().year
    anios_rango = list(range(anio_actual - 5, anio_actual + 1))
    obras_por_anio_raw = (
        Articulo.objects.filter(en_papelera=False, estado='aprobado', año_produccion__in=anios_rango)
        .values('año_produccion')
        .annotate(total=Count('id'))
    )
    obras_por_anio_dict = {item['año_produccion']: item['total'] for item in obras_por_anio_raw}
    chart_anios_labels = [str(y) for y in anios_rango]
    chart_anios_data = [obras_por_anio_dict.get(y, 0) for y in anios_rango]

    # Distribución por Área
    obras_area_qs = list(
        Articulo.objects.filter(en_papelera=False, estado='aprobado', area__isnull=False)
        .values('area__nombre')
        .annotate(total=Count('id'))
        .order_by('-total')[:6]
    )
    chart_areas_labels = [x['area__nombre'] for x in obras_area_qs]
    chart_areas_data = [x['total'] for x in obras_area_qs]

    # Distribución por Tipo de Obra
    obras_tipo_qs = list(
        Articulo.objects.filter(en_papelera=False, estado='aprobado', tipo_contenido__isnull=False)
        .values('tipo_contenido__nombre')
        .annotate(total=Count('id'))
        .order_by('-total')[:6]
    )
    chart_tipos_labels = [x['tipo_contenido__nombre'] for x in obras_tipo_qs]
    chart_tipos_data = [x['total'] for x in obras_tipo_qs]

    # Ranking Top 5 Investigadores Prolíficos
    ranking_top_autores = (
        Autor.objects.annotate(
            total_aprob=Count('documentos', filter=Q(documentos__estado='aprobado', documentos__en_papelera=False), distinct=True)
        )
        .filter(total_aprob__gt=0)
        .order_by('-total_aprob')[:5]
    )

    # KPIs globales
    total_obras_aprobadas_metric = Articulo.objects.filter(en_papelera=False, estado='aprobado').count()
    total_con_doi_metric = Articulo.objects.filter(en_papelera=False, estado='aprobado').exclude(doi_enlace='').exclude(doi_enlace__isnull=True).count()
    porcentaje_doi = int((total_con_doi_metric / total_obras_aprobadas_metric * 100)) if total_obras_aprobadas_metric > 0 else 0
    total_docentes_con_obras = Autor.objects.filter(documentos__estado='aprobado', documentos__en_papelera=False).distinct().count()

    context = {
        'pendientes': pendientes,
        'suspendidas': suspendidas,
        'administrativos': administrativos,
        'superusuarios': superusuarios,
        'todos_documentos': todos_documentos,
        'documentos_pendientes': documentos_pendientes,
        'subidas_automaticas': subidas_automaticas,
        'semblanzas_pendientes': Autor.objects.filter(usuario__isnull=False, estado_semblanza='pendiente'),
        'todas_semblanzas': todas_semblanzas,
        'autores_catalogo': autores_catalogo,
        'total_autores_catalogo': Autor.objects.count(),
        'todos_los_autores_simple': Autor.objects.order_by('nombre'),
        'total_huerfanos': total_huerfanos,
        'total_huerfanos_inactivos': total_huerfanos_inactivos,
        'total_huerfanos_recientes': total_huerfanos_recientes,
        'lista_huerfanos': lista_huerfanos,
        'limite_15m': limite_15m,
        'grupos_parecidos': grupos_parecidos,
        'total_grupos_parecidos': len(grupos_parecidos),
        'fusiones_recientes': fusiones_recientes,
        'total_fusiones_hoy': total_fusiones_hoy,
        'q_docs': q_docs,
        'q_semb': q_semb,
        'q_autores': q_autores,
        'areas_catalogo': Area.objects.all().order_by('nombre'),
        'tipos_catalogo': TipoContenido.objects.all().order_by('nombre'),
        'ids_candidatos_confianza': ids_candidatos_confianza,
        'rachas_aprobadas_por_usuario': rachas_aprobadas_por_usuario,
        'total_candidatos_confianza': len(ids_candidatos_confianza),
        'total_candidatos_sin_credencial': total_candidatos_sin_credencial,
        'subidas_auto_pendientes_chequeo': subidas_auto_pendientes_chequeo,
        'subidas_auto_total': subidas_auto_total,
        'documentos_papelera': documentos_papelera_qs,
        'total_papelera': total_papelera,
        'es_principal': es_superusuario_principal(request.user),
        'registros': registros.order_by('-created_at'),
        'fecha_seleccionada': fecha_filtro,
        'roles_docente': ROL_DOCENTE_OPCIONES,
        'chart_anios_labels_json': json.dumps(chart_anios_labels),
        'chart_anios_data_json': json.dumps(chart_anios_data),
        'chart_areas_labels_json': json.dumps(chart_areas_labels),
        'chart_areas_data_json': json.dumps(chart_areas_data),
        'chart_tipos_labels_json': json.dumps(chart_tipos_labels),
        'chart_tipos_data_json': json.dumps(chart_tipos_data),
        'ranking_top_autores': ranking_top_autores,
        'metric_total_aprobadas': total_obras_aprobadas_metric,
        'metric_total_con_doi': total_con_doi_metric,
        'metric_porcentaje_doi': porcentaje_doi,
        'metric_docentes_activos': total_docentes_con_obras,
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

        # Validar que el remitente sea un colega docente, investigador, de otra universidad o superusuario
        tiene_perfil = hasattr(request.user, 'autor') or request.user.is_superuser
        if not tiene_perfil:
            messages.error(request, 'Debes contar con una cuenta registrada para enviar felicitaciones de cumpleaños.')
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


@login_required
def cambiar_color_cumpleanos_view(request):
    """
    Permite al docente personalizar el sabor y color de su tarjeta cupcake de cumpleaños.
    """
    if request.method == 'POST':
        autor = getattr(request.user, 'autor', None)
        if not autor:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                return JsonResponse({'status': 'error', 'message': 'No se encontró un perfil docente asociado.'}, status=400)
            messages.error(request, 'No tienes un perfil docente asociado.')
            return redirect('mi_panel')

        color = request.POST.get('color', '').strip().lower()
        colores_validos = dict(Autor.COLORES_CUMPLEANOS)

        if color not in colores_validos:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'status': 'error', 'message': 'Opción de color no válida.'}, status=400)
            messages.error(request, 'Opción de color no válida.')
            return redirect(request.META.get('HTTP_REFERER', 'mi_panel'))

        autor.color_cumpleanos = color
        autor.save(update_fields=['color_cumpleanos'])

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'ok',
                'color': color,
                'color_display': colores_validos[color],
                'message': f'¡Estilo de cupcake actualizado a "{colores_validos[color]}" exitosamente!'
            })

        messages.success(request, f'¡Estilo de cupcake actualizado a "{colores_validos[color]}"!')
        return redirect(request.META.get('HTTP_REFERER', 'mi_panel'))

    return redirect('mi_panel')


@user_passes_test(es_superusuario, login_url='/login/')
def aprobar_documento_view(request, doc_id):
    articulo = get_object_or_404(Articulo, id=doc_id)
    articulo.estado = 'aprobado'
    articulo.motivo_rechazo = ''
    articulo.moderado_por = request.user
    articulo.save()

    try:
        notificar_obra_aprobada(articulo)
    except Exception as e:
        logger.warning(f"Error al enviar correo de obra aprobada: {e}")

    registrar_auditoria(request.user, "Aprobación de Documento", f"Aprobó la obra: {articulo.titulo}")
    messages.success(request, f'La obra "{articulo.titulo}" ha sido aprobada y publicada exitosamente.')
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
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

        try:
            notificar_obra_rechazada(articulo, motivo_final)
        except Exception as e:
            logger.warning(f"Error al enviar correo de obra rechazada: {e}")

        registrar_auditoria(request.user, "Rechazo de Documento", f"Rechazó la obra: {articulo.titulo}")
        messages.warning(request,
                         f'La obra "{articulo.titulo}" ha sido devuelta al autor con observaciones de corrección.')
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def marcar_archivo_checado_view(request, doc_id):
    articulo = get_object_or_404(Articulo, id=doc_id)
    articulo.chequeado_por_moderador = True
    articulo.chequeado_por = request.user
    articulo.fecha_chequeado = timezone.now()
    articulo.save()

    registrar_auditoria(
        request.user,
        "Cotejo de Obra de Confianza",
        f"Verificó y marcó como «Archivo Checado» la publicación directa: {articulo.titulo}"
    )
    messages.success(request, f'La obra de publicación directa "{articulo.titulo}" ha sido verificada y marcada como «Archivo Checado».')
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect(f"{reverse('panel_usuarios')}#documentos")


@user_passes_test(es_superusuario, login_url='/login/')
def acciones_masivas_documentos_view(request):
    """Ejecuta acciones en lote (aprobar, cotejar, eliminar) sobre múltiples documentos seleccionados."""
    if request.method == 'POST':
        accion = request.POST.get('accion', '').strip()
        ids_raw = request.POST.get('doc_ids', '').strip()
        try:
            doc_ids = json.loads(ids_raw) if ids_raw.startswith('[') else [int(x.strip()) for x in ids_raw.split(',') if x.strip()]
        except Exception:
            doc_ids = []

        if not doc_ids:
            messages.warning(request, "No seleccionaste ningún documento para aplicar la acción en lote.")
            return redirect(f"{reverse('panel_usuarios')}#documentos")

        docs = Articulo.objects.filter(id__in=doc_ids)
        total_afectados = docs.count()

        if accion == 'aprobar':
            docs.update(estado='aprobado', motivo_rechazo='', moderado_por=request.user)
            registrar_auditoria(request.user, "Aprobación Masiva", f"Aprobó {total_afectados} obras en lote (IDs: {doc_ids})")
            messages.success(request, f"Se han aprobado y publicado exitosamente {total_afectados} obras académicas en lote.")
        elif accion == 'checar':
            chequeados = docs.filter(es_subida_automatica=True).update(
                chequeado_por_moderador=True,
                chequeado_por=request.user,
                fecha_chequeado=timezone.now()
            )
            registrar_auditoria(request.user, "Cotejo Masivo", f"Marcó como checadas {chequeados} publicaciones de confianza")
            messages.success(request, f"Se verificaron y marcaron como «Archivo Checado» {chequeados} publicaciones de confianza.")
        elif accion == 'eliminar':
            docs.update(en_papelera=True, fecha_eliminacion=timezone.now(), eliminado_por=request.user)
            registrar_auditoria(request.user, "Envío Masivo a Papelera", f"Movió a la papelera {total_afectados} obras en lote (IDs: {doc_ids})")
            messages.success(request, f"Se han movido {total_afectados} obras a la Papelera de Reciclaje (puedes restaurarlas en cualquier momento).")
        elif accion == 'restaurar':
            docs.update(en_papelera=False, fecha_eliminacion=None, eliminado_por=None)
            registrar_auditoria(request.user, "Restauración Masiva", f"Restauró de la papelera {total_afectados} obras en lote (IDs: {doc_ids})")
            messages.success(request, f"Se han restaurado {total_afectados} obras de la Papelera al catálogo activo.")
        elif accion == 'purgar':
            titulos = list(docs.values_list('titulo', flat=True)[:5])
            docs.delete()
            try:
                limpiar_autores_huerfanos(minutos_gracia=0)
            except Exception:
                pass
            registrar_auditoria(request.user, "Eliminación Masiva Definitiva", f"Eliminó permanentemente {total_afectados} obras en lote: {', '.join(titulos)}")
            messages.success(request, f"Se han eliminado permanentemente {total_afectados} obras de la base de datos.")
        else:
            messages.error(request, "Acción en lote no reconocida.")

    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect(f"{reverse('panel_usuarios')}#documentos")


@user_passes_test(es_superusuario, login_url='/login/')
def exportar_documentos_excel_view(request):
    """Genera y descarga un reporte en formato CSV con BOM UTF-8 (compatible con Excel) de las obras filtradas o seleccionadas."""
    import csv
    from django.http import HttpResponse

    ids_raw = request.GET.get('ids', '').strip()
    estado = request.GET.get('estado', '').strip()
    area_id = request.GET.get('area_id', '').strip()
    tipo_id = request.GET.get('tipo_id', '').strip()
    q_search = request.GET.get('q', '').strip()

    docs = Articulo.objects.all().order_by('-created_at')

    if ids_raw:
        try:
            ids_list = [int(x) for x in ids_raw.split(',') if x.strip()]
            docs = docs.filter(id__in=ids_list)
        except Exception:
            pass
    else:
        if estado and estado != 'all':
            if estado == 'automatico':
                docs = docs.filter(es_subida_automatica=True)
            else:
                docs = docs.filter(estado=estado)
        if area_id and area_id != 'all':
            docs = docs.filter(area_id=area_id)
        if tipo_id and tipo_id != 'all':
            docs = docs.filter(tipo_contenido_id=tipo_id)
        if q_search:
            docs = docs.filter(
                Q(titulo__icontains=q_search) |
                Q(autor__nombre__icontains=q_search) |
                Q(subido_por__username__icontains=q_search) |
                Q(palabras_clave__icontains=q_search)
            ).distinct()

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"reporte_obras_fca_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'ID',
        'Título de la Obra',
        'Tipo de Recurso',
        'Área de Conocimiento',
        'Autores Acreditados',
        'Año de Producción',
        'Estado Editorial',
        'DOI / Enlace',
        'ISBN / ISSN',
        'Revista / Editorial',
        'Subido Por',
        'Fecha de Carga',
        'Subida Directa (Confianza)',
        'Cotejado por Moderador',
        'Resumen'
    ])

    for doc in docs:
        autores_txt = ", ".join([a.nombre for a in doc.autor.all()])
        writer.writerow([
            doc.id,
            doc.titulo,
            doc.tipo_contenido.nombre if doc.tipo_contenido else '',
            doc.area.nombre if doc.area else '',
            autores_txt or 'Sin autor',
            doc.año_produccion or '',
            doc.get_estado_display() if hasattr(doc, 'get_estado_display') else doc.estado,
            doc.doi_enlace or '',
            doc.isbn_issn or '',
            doc.revista or doc.editorial or '',
            doc.subido_por.username if doc.subido_por else 'Admin / Inicial',
            doc.created_at.strftime('%d/%m/%Y %H:%M') if doc.created_at else '',
            'Sí' if doc.es_subida_automatica else 'No',
            'Sí' if doc.chequeado_por_moderador else 'No',
            (doc.descripcion or '').replace('\n', ' ').replace('\r', '')[:300]
        ])

    registrar_auditoria(request.user, "Exportación de Reporte", f"Descargó reporte de obras académicas ({docs.count()} registros)")
    return response


@login_required
def eliminar_documento_view(request, doc_id):
    articulo = get_object_or_404(Articulo, id=doc_id)

    if not (request.user.is_superuser or articulo.subido_por == request.user):
        messages.error(request, "No tienes autorización para eliminar esta obra.")
        return redirect('mi_panel')

    titulo_doc = articulo.titulo
    es_definitivo = request.GET.get('definitivo') == '1' or request.POST.get('definitivo') == '1'

    if es_definitivo or articulo.en_papelera:
        articulo.delete()
        try:
            limpiar_autores_huerfanos(minutos_gracia=0)
        except Exception:
            pass
        registrar_auditoria(request.user, "Eliminación Definitiva de Obra", f"Purgó permanentemente la obra: {titulo_doc}")
        messages.success(request, f'La obra "{titulo_doc}" ha sido eliminada permanentemente del sistema.')
    else:
        articulo.en_papelera = True
        articulo.fecha_eliminacion = timezone.now()
        articulo.eliminado_por = request.user
        articulo.save()
        registrar_auditoria(request.user, "Envío a Papelera", f"Movió a la papelera la obra: {titulo_doc}")
        messages.success(request, f'La obra "{titulo_doc}" fue movida a la Papelera de Reciclaje. Puedes restaurarla cuando lo desees.')

    referer = request.META.get('HTTP_REFERER', '')
    if 'ver-subidas' in referer:
        return redirect(referer)
    if 'gestion-usuarios' in referer:
        return redirect(f"{reverse('panel_usuarios')}#documentos")
    return redirect('mi_panel')


@login_required
def restaurar_documento_view(request, doc_id):
    articulo = get_object_or_404(Articulo, id=doc_id)
    if not (request.user.is_superuser or articulo.subido_por == request.user):
        messages.error(request, "No tienes autorización para restaurar esta obra.")
        return redirect('mi_panel')

    titulo_doc = articulo.titulo
    articulo.en_papelera = False
    articulo.fecha_eliminacion = None
    articulo.eliminado_por = None
    articulo.save()

    registrar_auditoria(request.user, "Restauración de Obra", f"Restauró de la papelera la obra: {titulo_doc}")
    messages.success(request, f'La obra "{titulo_doc}" ha sido restaurada con éxito al catálogo activo.')

    referer = request.META.get('HTTP_REFERER', '')
    if 'gestion-usuarios' in referer:
        return redirect(f"{reverse('panel_usuarios')}#documentos")
    return redirect('mi_panel')


@user_passes_test(es_superusuario, login_url='/login/')
def vaciar_papelera_documentos_view(request):
    """Vacía definitivamente todas las obras en la papelera de reciclaje."""
    docs_papelera = Articulo.objects.filter(en_papelera=True)
    total = docs_papelera.count()
    if total > 0:
        docs_papelera.delete()
        try:
            limpiar_autores_huerfanos(minutos_gracia=0)
        except Exception:
            pass
        registrar_auditoria(request.user, "Vaciado de Papelera", f"Eliminó permanentemente {total} obras de la papelera")
        messages.success(request, f"Se han eliminado permanentemente {total} obra(s) de la Papelera de Reciclaje.")
    else:
        messages.info(request, "La papelera ya se encuentra vacía.")
    return redirect(f"{reverse('panel_usuarios')}#documentos")


@user_passes_test(es_superusuario, login_url='/login/')
def exportar_respaldo_sistema_view(request):
    """Genera y descarga un snapshot completo del repositorio en formato JSON (.json)."""
    modelos = [
        User, Area, TipoContenido, Entidad, Universidad, Nombramiento,
        Autor, EnlaceProfesional, Articulo, InvitacionCoautoria,
        MensajeInterno, MensajeCumpleanos, HistorialFusion, RegistroAuditoria
    ]

    todos_objetos = []
    stats = {}
    for mod in modelos:
        qs = mod.objects.all()
        stats[mod.__name__] = qs.count()
        todos_objetos.extend(list(qs))

    fixtures_json = serializers.serialize('json', todos_objetos, indent=2)
    fixtures_data = json.loads(fixtures_json)

    payload = {
        'backup_version': '2.0',
        'sistema': 'Repositorio FCA - Universidad Autónoma de Baja California',
        'fecha_generacion': timezone.now().isoformat(),
        'generado_por': request.user.username,
        'estadisticas': stats,
        'total_registros': len(fixtures_data),
        'fixtures': fixtures_data
    }

    json_bytes = json.dumps(payload, indent=2, ensure_ascii=False).encode('utf-8')
    filename = f"backup_fca_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"
    response = HttpResponse(json_bytes, content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    registrar_auditoria(request.user, "Generación de Respaldo", f"Descargó copia de seguridad del sistema ({len(fixtures_data)} registros)")
    return response


@user_passes_test(es_superusuario, login_url='/login/')
def restaurar_respaldo_sistema_view(request):
    """
    Lee y restaura de forma limpia y atómica los datos del archivo .json cargado por el superusuario ('Poner backup aquí').
    Garantiza que no ocurran conflictos de clave duplicada (UNIQUE constraints) con cuentas o datos creados posteriormente.
    """
    if request.method != 'POST':
        messages.warning(request, "Método no permitido para restauración.")
        return redirect(f"{reverse('panel_usuarios')}#documentos")

    archivo = request.FILES.get('archivo_backup')
    if not archivo:
        messages.error(request, "No seleccionaste ningún archivo de respaldo.")
        return redirect(f"{reverse('panel_usuarios')}#documentos")

    if not archivo.name.lower().endswith('.json'):
        messages.error(request, "El archivo debe tener formato .json válido de copia de seguridad.")
        return redirect(f"{reverse('panel_usuarios')}#documentos")

    try:
        contenido = archivo.read().decode('utf-8')
        data = json.loads(contenido)
    except Exception as e:
        messages.error(request, f"Error al procesar el archivo JSON: {str(e)}")
        return redirect(f"{reverse('panel_usuarios')}#documentos")

    fixtures = data.get('fixtures')
    if not isinstance(fixtures, list):
        if isinstance(data, list):
            fixtures = data
        else:
            messages.error(request, "El archivo no contiene un formato de respaldo compatible de Django / FCA.")
            return redirect(f"{reverse('panel_usuarios')}#documentos")

    if not fixtures:
        messages.warning(request, "El archivo de respaldo está vacío (0 registros). No se realizaron cambios.")
        return redirect(f"{reverse('panel_usuarios')}#documentos")

    try:
        with transaction.atomic():
            admin_actual = request.user
            admin_actual_id = admin_actual.id
            admin_username_lower = admin_actual.username.lower()

            # 1. Identificar usuarios presentes en el archivo de respaldo
            fixture_users = [item for item in fixtures if item.get('model') == 'auth.user']
            backup_usernames = {
                item.get('fields', {}).get('username', '').lower(): item.get('pk')
                for item in fixture_users if 'username' in item.get('fields', {})
            }

            # 2. Si el admin actual viene en el backup pero con un ID numérico diferente,
            # remapeamos ese ID en los fixtures para evitar choques de integridad y conservar su sesión viva.
            id_mapeo_admin = {}
            if admin_username_lower in backup_usernames:
                backup_admin_pk = backup_usernames[admin_username_lower]
                if backup_admin_pk != admin_actual_id:
                    id_mapeo_admin[backup_admin_pk] = admin_actual_id

            if id_mapeo_admin:
                fk_user_fields_map = [
                    'usuario', 'subido_por', 'moderado_por', 'chequeado_por',
                    'suspendido_por', 'admin_usuario', 'revertida_por',
                    'moderado_por_semblanza', 'usuario_responsable', 'de_usuario',
                    'remitente', 'destinatario'
                ]
                for item in fixtures:
                    if item.get('model') == 'auth.user' and item.get('pk') in id_mapeo_admin:
                        item['pk'] = id_mapeo_admin[item.get('pk')]
                    fields = item.get('fields', {})
                    for fk_name in fk_user_fields_map:
                        if fk_name in fields and fields[fk_name] in id_mapeo_admin:
                            fields[fk_name] = id_mapeo_admin[fields[fk_name]]

            # 3. Vaciado limpio de tablas del repositorio antes de inyectar el snapshot.
            # Esto previene CUALQUIER colisión de:
            # - UNIQUE constraint en username o email de User
            # - UNIQUE constraint en OneToOneField Autor.usuario
            # - UNIQUE constraint en Autor.codigo_institucional
            # - UNIQUE constraint en Universidad.nombre
            InvitacionCoautoria.objects.all().delete()
            Articulo.objects.all().delete()
            EnlaceProfesional.objects.all().delete()
            Nombramiento.objects.all().delete()
            HistorialFusion.objects.all().delete()
            MensajeInterno.objects.all().delete()
            MensajeCumpleanos.objects.all().delete()
            Autor.objects.all().delete()
            RegistroAuditoria.objects.all().delete()
            Universidad.objects.all().delete()
            TipoContenido.objects.all().delete()
            Area.objects.all().delete()
            Entidad.objects.all().delete()

            # Eliminar usuarios creados a posteriori que no sean el administrador actual
            User.objects.exclude(id=admin_actual_id).delete()

            # 4. Sanitizar FKs a User para IDs que no existan en el snapshot
            user_ids_disponibles = {admin_actual_id}
            for item in fixtures:
                if item.get('model') == 'auth.user':
                    user_ids_disponibles.add(item.get('pk'))

            fk_user_fields = [
                'usuario', 'subido_por', 'moderado_por', 'chequeado_por',
                'suspendido_por', 'admin_usuario', 'revertida_por',
                'moderado_por_semblanza', 'usuario_responsable', 'de_usuario',
                'remitente', 'destinatario'
            ]
            for item in fixtures:
                fields = item.get('fields', {})
                for fk_name in fk_user_fields:
                    if fk_name in fields and fields[fk_name] and fields[fk_name] not in user_ids_disponibles:
                        fields[fk_name] = None

            # 5. Deserializar los registros del JSON y ordenarlos por dependencias de modelos
            MODEL_ORDER = {
                'auth.user': 1,
                'pagina.entidad': 2,
                'pagina.area': 2,
                'pagina.tipocontenido': 2,
                'pagina.universidad': 2,
                'pagina.autor': 3,
                'pagina.nombramiento': 4,
                'pagina.enlaceprofesional': 4,
                'pagina.articulo': 5,
                'pagina.invitacioncoautoria': 6,
                'pagina.historialfusion': 6,
                'pagina.mensajeinterno': 6,
                'pagina.mensajecumpleanos': 6,
                'pagina.registroauditoria': 6,
            }

            from django.db import connection
            is_mysql = connection.vendor == 'mysql'
            is_sqlite = connection.vendor == 'sqlite'
            with connection.cursor() as cursor:
                if is_mysql:
                    cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
                elif is_sqlite:
                    cursor.execute("PRAGMA foreign_keys = OFF;")

            try:
                deserializados = list(serializers.deserialize('json', json.dumps(fixtures)))
                deserializados.sort(key=lambda o: MODEL_ORDER.get(getattr(o.object._meta, 'label_lower', ''), 99))

                total_guardados = 0
                for obj in deserializados:
                    if isinstance(obj.object, User):
                        if obj.object.id == admin_actual_id or obj.object.username.lower() == admin_username_lower:
                            # Mantener intacta la sesión del administrador
                            admin_user = User.objects.get(id=admin_actual_id)
                            admin_user.is_active = True
                            admin_user.is_staff = True
                            admin_user.is_superuser = True
                            admin_user.save()
                            total_guardados += 1
                            continue
                    obj.save()
                    total_guardados += 1
            finally:
                with connection.cursor() as cursor:
                    if is_mysql:
                        cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
                    elif is_sqlite:
                        cursor.execute("PRAGMA foreign_keys = ON;")

            # 6. Resetear las secuencias de auto-increment en la base de datos (PostgreSQL / SQLite / MySQL)
            try:
                from django.core.management.color import no_style
                from django.db import connection
                modelos_secuencia = [
                    User, Area, TipoContenido, Entidad, Universidad, Nombramiento,
                    Autor, EnlaceProfesional, Articulo, InvitacionCoautoria,
                    MensajeInterno, MensajeCumpleanos, HistorialFusion, RegistroAuditoria
                ]
                sequence_sql = connection.ops.sequence_reset_sql(no_style(), modelos_secuencia)
                if sequence_sql:
                    with connection.cursor() as cursor:
                        for sql in sequence_sql:
                            cursor.execute(sql)
            except Exception as seq_err:
                logger.warning(f"Aviso al resetear secuencias de base de datos tras restaurar: {seq_err}")

        registrar_auditoria(
            request.user,
            "Restauración de Respaldo",
            f"Restauró el repositorio desde el archivo: {archivo.name} ({total_guardados} registros sincronizados)"
        )
        messages.success(request, f"¡Respaldo restaurado con éxito! Se sincronizaron {total_guardados} registros en la base de datos sin errores ni conflictos.")
    except Exception as e:
        logger.exception("Error durante la restauración del respaldo")
        messages.error(request, f"Error durante la restauración del respaldo: {str(e)}. La base de datos no fue modificada.")

    return redirect(f"{reverse('panel_usuarios')}#documentos")


@user_passes_test(es_superusuario, login_url='/login/')
def aprobar_usuario_view(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    usuario.is_active = True
    usuario.save()
    if hasattr(usuario, 'autor') and usuario.autor:
        usuario.autor.estado_cuenta = 'activa'
        usuario.autor.correo_verificado = True
        usuario.autor.codigo_verificacion = None
        usuario.autor.codigo_verificacion_expira = None
        usuario.autor.motivo_suspension = ''
        usuario.autor.fecha_fin_suspension = None
        usuario.autor.fecha_suspension = None
        usuario.autor.suspendido_por = None
        usuario.autor.save()
        if usuario.autor.es_auxiliar and usuario.autor.profesor_tutor:
            try:
                MensajeInterno.objects.create(
                    remitente=request.user,
                    destinatario=usuario.autor.profesor_tutor,
                    asunto=f"Cuenta de Auxiliar Activada: {usuario.autor.nombre}",
                    cuerpo=f"La cuenta de tu Auxiliar de Investigación FCA, {usuario.autor.nombre} (Matrícula: {usuario.autor.matricula_estudiante or 'S/N'}), ha sido aprobada y activada por el Super Administrador.",
                    es_soporte=False
                )
            except Exception:
                pass

        perfil_desc = 'Usuario FCA'
        if usuario.autor.es_auxiliar:
            perfil_desc = 'Auxiliar de Investigación FCA'
        elif usuario.autor.es_operador_tecnico:
            perfil_desc = 'Operador Técnico / Depurador de Contenidos'
        elif usuario.autor.es_soporte:
            perfil_desc = 'Soporte Técnico (Modo Lector)'
        elif usuario.autor.es_profesor:
            perfil_desc = 'Docente / Investigador UABC'
        elif usuario.autor.es_externo:
            perfil_desc = 'Colaborador Externo'

        try:
            notificar_aprobacion_cuenta(usuario, perfil_desc)
        except Exception as e:
            pass

    registrar_auditoria(request.user, "Aprobación de Solicitud de Usuario", f"Aprobó la cuenta de: {usuario.username}")
    if hasattr(usuario, 'autor') and usuario.autor and usuario.autor.es_soporte:
        messages.success(request, f'La cuenta de Soporte Técnico "{usuario.username}" ha sido activada en Modo Lector. Puedes otorgarle facultades totales mediante el botón "Ascender a Super Administrador".')
    else:
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
def suspender_usuario_view(request, user_id):
    """Suspende una cuenta registrando motivo obligatorio y tiempo definido (o indefinido)."""
    if request.method == 'POST':
        usuario = get_object_or_404(User, id=user_id)
        if usuario == request.user or (usuario.id == 1 or usuario.username.lower() == 'yaele'):
            messages.error(request, 'No puedes suspender a este usuario protegido.')
            return redirect('panel_usuarios')

        if not es_superusuario_principal(request.user):
            admin_pass = request.POST.get('admin_password', '').strip()
            if not request.user.check_password(admin_pass):
                messages.error(request, 'Contraseña de administrador incorrecta. No se pudo suspender la cuenta.')
                return redirect('panel_usuarios')

        motivo = request.POST.get('motivo_suspension', '').strip()
        duracion = request.POST.get('duracion', 'indefinida')

        if not motivo:
            messages.error(request, 'Es obligatorio especificar el motivo de la suspensión para el registro institucional.')
            return redirect('panel_usuarios')

        fecha_fin = None
        ahora = timezone.now()
        tiempo_texto = "tiempo indefinido"

        if duracion == '2h':
            fecha_fin = ahora + timedelta(hours=2)
            tiempo_texto = "2 horas"
        elif duracion == '5h':
            fecha_fin = ahora + timedelta(hours=5)
            tiempo_texto = "5 horas"
        elif duracion == '24h':
            fecha_fin = ahora + timedelta(hours=24)
            tiempo_texto = "24 horas (1 día)"
        elif duracion == '3d':
            fecha_fin = ahora + timedelta(days=3)
            tiempo_texto = "3 días"
        elif duracion == '7d':
            fecha_fin = ahora + timedelta(days=7)
            tiempo_texto = "7 días"
        elif duracion == '30d':
            fecha_fin = ahora + timedelta(days=30)
            tiempo_texto = "30 días"

        usuario.is_active = False
        usuario.save()

        autor, _ = Autor.objects.get_or_create(
            usuario=usuario,
            defaults={'nombre': usuario.get_full_name() or usuario.username, 'correo': usuario.email}
        )
        autor.estado_cuenta = 'suspendida'
        autor.motivo_suspension = motivo
        autor.fecha_suspension = ahora
        autor.fecha_fin_suspension = fecha_fin
        autor.suspendido_por = request.user
        autor.save()

        detalle = f"Suspendió a: {usuario.username} por {tiempo_texto}. Motivo: {motivo}"
        registrar_auditoria(request.user, "Suspensión de Cuenta", detalle)
        messages.warning(request, f'La cuenta de "{usuario.username}" ha sido suspendida por {tiempo_texto}.')

    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def reactivar_usuario_view(request, user_id):
    """Reactiva una cuenta previamente suspendida o dada de baja."""
    if request.method == 'POST':
        usuario = get_object_or_404(User, id=user_id)

        if not es_superusuario_principal(request.user):
            admin_pass = request.POST.get('admin_password', '').strip()
            if not request.user.check_password(admin_pass):
                messages.error(request, 'Contraseña de administrador incorrecta. No se pudo reactivar la cuenta.')
                return redirect('panel_usuarios')

        usuario.is_active = True
        usuario.save()

        if hasattr(usuario, 'autor') and usuario.autor:
            autor = usuario.autor
            autor.estado_cuenta = 'activa'
            autor.motivo_suspension = ''
            autor.fecha_fin_suspension = None
            autor.fecha_suspension = None
            autor.suspendido_por = None
            autor.solicitud_reactivacion = False
            autor.motivo_reactivacion = ''
            autor.fecha_solicitud_reactivacion = None
            autor.contacto_reactivacion = ''
            autor.save()

        # Resolver tickets de soporte asociados
        MensajeInterno.objects.filter(
            remitente=usuario,
            es_soporte=True,
            asunto__icontains="Reactivación"
        ).update(estado_soporte='resuelto', atendido_por=request.user)

        registrar_auditoria(request.user, "Reactivación de Cuenta", f"Reactivó el acceso al usuario: {usuario.username}")
        messages.success(request, f'La cuenta de "{usuario.username}" ha sido reactivada exitosamente.')

    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def toggle_trusted_publisher_view(request, user_id):
    """Otorga o revoca la credencial de Publicador de Confianza (Bypass de Moderación)."""
    if request.method == 'POST':
        usuario = get_object_or_404(User, id=user_id)
        autor, _ = Autor.objects.get_or_create(
            usuario=usuario,
            defaults={'nombre': usuario.get_full_name() or usuario.username, 'correo': usuario.email}
        )
        autor.is_trusted_publisher = not autor.is_trusted_publisher
        autor.save()

        accion_txt = "otorgó" if autor.is_trusted_publisher else "retiró"
        registrar_auditoria(
            request.user,
            "Cambio de Permiso Trusted Publisher",
            f"{accion_txt.capitalize()} credencial de Publicador de Confianza a: {usuario.username}"
        )

        return JsonResponse({
            'success': True,
            'is_trusted': autor.is_trusted_publisher,
            'message': f'Se {accion_txt} la credencial de Publicador de Confianza a "{usuario.username}".'
        })
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)


@login_required
def desactivar_cuenta_propia_view(request):
    """Soft Delete: El usuario desactiva su propia cuenta desde Mi Panel."""
    if request.method == 'POST':
        user = request.user
        if user.is_superuser or user.id == 1 or user.username.lower() == 'yaele':
            messages.error(request, 'Las cuentas de administrador principal no pueden darse de baja directamente por esta vía.')
            return redirect('mi_panel')

        pass_actual = request.POST.get('password_confirmacion', '').strip()
        if not user.check_password(pass_actual):
            messages.error(request, 'La contraseña ingresada es incorrecta. No se pudo desactivar la cuenta.')
            return redirect('mi_panel')

        user.is_active = False
        user.save()

        if hasattr(user, 'autor') and user.autor:
            autor = user.autor
            autor.estado_cuenta = 'baja_voluntaria'
            autor.motivo_suspension = 'Baja solicitada voluntariamente por el usuario titular'
            autor.fecha_suspension = timezone.now()
            autor.fecha_fin_suspension = None
            autor.save()

        registrar_auditoria(None, "Baja Voluntaria de Cuenta (Soft Delete)", f"El usuario {user.username} dio de baja su propia cuenta.")
        logout(request)
        messages.info(
            request,
            'Tu cuenta ha sido desactivada correctamente. Tus obras académicas continúan resguardadas e intactas en el repositorio. Si en algún momento deseas reactivar tu cuenta, ponte en contacto con la administración de FCA.'
        )
        return redirect('/')

    return redirect('mi_panel')


def solicitar_reactivacion_view(request):
    """Permite a usuarios con cuenta suspendida o dada de baja voluntariamente solicitar su reactivación."""
    if request.method == 'POST':
        login_input = request.POST.get('username_o_email', '').strip()
        motivo = request.POST.get('motivo', '').strip()
        contacto = request.POST.get('contacto', '').strip()
        password_check = request.POST.get('password_validacion', '').strip()

        if not login_input:
            messages.error(request, 'Por favor ingresa tu nombre de usuario o correo institucional.')
            return redirect('login')

        usuario = User.objects.filter(
            Q(username__iexact=login_input) | Q(email__iexact=login_input)
        ).first()

        if not usuario:
            messages.error(request, f'No se encontró ninguna cuenta asociada a "{login_input}". Verifica que esté escrita correctamente.')
            return redirect('login')

        if usuario.is_active:
            messages.info(request, f'La cuenta "{usuario.username}" ya se encuentra activa. Puedes iniciar sesión directamente.')
            return redirect('login')

        autor = getattr(usuario, 'autor', None)
        if not autor or autor.estado_cuenta not in ['baja_voluntaria', 'suspendida']:
            messages.warning(request, 'Tu cuenta se encuentra en proceso de validación inicial o en un estado que no requiere este procedimiento.')
            return redirect('login')

        if password_check and not usuario.check_password(password_check):
            messages.error(request, 'La contraseña ingresada no coincide con los registros de la cuenta.')
            return redirect('login')

        # Registrar la solicitud en el modelo Autor
        autor.solicitud_reactivacion = True
        autor.motivo_reactivacion = motivo or "Solicitud de reactivación y recuperación de acceso a la cuenta."
        autor.fecha_solicitud_reactivacion = timezone.now()
        autor.contacto_reactivacion = contacto or usuario.email
        autor.save()

        # Generar ticket en la Mesa de Ayuda / Soporte Interno
        tipo_baja = "Baja Voluntaria por el Usuario" if autor.estado_cuenta == 'baja_voluntaria' else "Suspensión Administrativa"
        cuerpo_ticket = (
            f"El usuario @{usuario.username} ({autor.nombre or usuario.username}) ha solicitado formalmente la REACTIVACIÓN de su cuenta.\n\n"
            f"Tipo de estado previo: {tipo_baja}\n"
            f"Correo institucional registrado: {usuario.email}\n"
            f"Contacto alternativo proporcionado: {contacto or 'No especificado'}\n\n"
            f"Mensaje / Motivo de la solicitud:\n"
            f"«{motivo or 'Deseo reincorporarme y reactivar mi cuenta en el repositorio.'}»\n\n"
            f"Acción recomendada: Puedes reactivar esta cuenta con un solo clic desde el panel de Gestión de Usuarios > Cuentas Suspendidas."
        )

        MensajeInterno.objects.create(
            remitente=usuario,
            es_soporte=True,
            asunto=f"Solicitud de Reactivación de Cuenta (@{usuario.username})",
            cuerpo=cuerpo_ticket,
            estado_soporte='abierto'
        )

        registrar_auditoria(
            None,
            "Solicitud de Reactivación de Cuenta",
            f"El usuario {usuario.username} ({tipo_baja}) envió una solicitud de reactivación de acceso."
        )

        messages.success(
            request,
            f'Tu solicitud de reactivación para la cuenta "@{usuario.username}" ha sido enviada con éxito al equipo de administración de FCA. '
            f'Se ha generado un ticket de atención y un administrador revisará tu cuenta a la brevedad.'
        )
        return redirect('login')

    return redirect('login')


@user_passes_test(es_superusuario, login_url='/login/')
def toggle_estado_usuario_view(request, user_id):
    """Compatibilidad: redirige hacia la lógica de reactivación si estaba inactiva o abre modal."""
    usuario = get_object_or_404(User, id=user_id)
    if not usuario.is_active:
        return reactivar_usuario_view(request, user_id)
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def toggle_superuser_view(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    if usuario.id == 1 or usuario.username.lower() == 'yaele':
        messages.error(request, 'No se pueden modificar los permisos del superusuario principal.')
        return redirect('panel_usuarios')

    # Si quien intenta ascender o degradar es un superusuario secundario, exigir su contraseña
    if not es_superusuario_principal(request.user):
        admin_pass = request.POST.get('admin_password', '').strip()
        if not admin_pass or not request.user.check_password(admin_pass):
            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1':
                return JsonResponse({'success': False, 'error': 'Contraseña de administrador incorrecta. Se requiere autenticación para modificar permisos de superusuario.'}, status=403)
            messages.error(request, 'Contraseña de administrador incorrecta. No se modificaron los privilegios.')
            return redirect('panel_usuarios')

    usuario.is_superuser = not usuario.is_superuser
    usuario.is_staff = True
    usuario.save()

    estado_super = "otorgó privilegios de Superusuario" if usuario.is_superuser else "retiró privilegios de Superusuario"
    registrar_auditoria(request.user, "Cambio de Privilegios Superusuario", f"{estado_super} a: {usuario.username}")
    
    if usuario.is_superuser:
        try:
            notificar_ascenso_superadmin(usuario)
        except Exception:
            pass

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1':
        return JsonResponse({
            'success': True,
            'is_superuser': usuario.is_superuser,
            'mensaje': f'Se han actualizado los privilegios de superusuario para "{usuario.username}".'
        })
    messages.success(request, f'Se han actualizado los privilegios de superusuario para "{usuario.username}".')
    return redirect('panel_usuarios')


@login_required
def gestionar_auxiliar_docente_view(request, auxiliar_id):
    """Permite al docente tutor otorgar su Visto Bueno o declinar a un Auxiliar de Investigación FCA."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    auxiliar = get_object_or_404(Autor, id=auxiliar_id, es_auxiliar=True)
    tutor_actual = getattr(request.user, 'autor', None)

    # Validar que el usuario sea el tutor asignado o un superusuario
    if not (request.user.is_superuser or (tutor_actual and auxiliar.profesor_tutor == tutor_actual)):
        return JsonResponse({'success': False, 'error': 'No tienes permisos para gestionar este auxiliar.'}, status=403)

    accion = request.POST.get('accion', 'aprobar')
    if accion == 'aprobar':
        auxiliar.aprobado_por_tutor = True
        auxiliar.fecha_aprobacion_tutor = timezone.now()
        auxiliar.save()

        # Registrar auditoría
        registrar_auditoria(
            request.user,
            "Visto Bueno de Auxiliar",
            f"El docente {request.user.username} otorgó Visto Bueno al auxiliar {auxiliar.nombre} (Matrícula: {auxiliar.matricula_estudiante or 'S/N'})."
        )

        # Notificar al auxiliar si tiene usuario (mensaje interno y correo)
        if auxiliar:
            try:
                MensajeInterno.objects.create(
                    remitente=request.user,
                    destinatario=auxiliar,
                    asunto="Visto Bueno otorgado por tu Profesor Tutor",
                    cuerpo=f"Tu profesor tutor ({request.user.autor.nombre if hasattr(request.user, 'autor') else request.user.username}) ha otorgado su Visto Bueno a tu vinculación académica. Tu cuenta ahora pasará a revisión final por el Super Administrador para su activación.",
                    es_soporte=False
                )
            except Exception:
                pass

            try:
                notificar_visto_bueno_auxiliar(auxiliar, auxiliar.profesor_tutor or tutor_actual)
            except Exception:
                pass

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1':
            return JsonResponse({'success': True, 'mensaje': f'Se ha otorgado el Visto Bueno a {auxiliar.nombre}.'})
        messages.success(request, f'Has otorgado el Visto Bueno al auxiliar {auxiliar.nombre}.')
        return redirect('mi_panel')

    elif accion == 'rechazar':
        nombre_aux = auxiliar.nombre
        auxiliar.aprobado_por_tutor = False
        auxiliar.profesor_tutor = None
        auxiliar.save()

        registrar_auditoria(
            request.user,
            "Rechazo de Vinculación de Auxiliar",
            f"El docente {request.user.username} declinó la vinculación del auxiliar {nombre_aux}."
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.POST.get('ajax') == '1':
            return JsonResponse({'success': True, 'mensaje': f'Se ha desvinculado a {nombre_aux}.'})
        messages.warning(request, f'Se ha rechazado la vinculación del auxiliar {nombre_aux}.')
        return redirect('mi_panel')

    return JsonResponse({'success': False, 'error': 'Acción desconocida'}, status=400)


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
            autor.es_auxiliar = False
            autor.es_operador_tecnico = False
            autor.es_soporte = False
        elif nuevo_rol == 'administrativo':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = False
            autor.es_externo = False
            autor.es_auxiliar = False
            autor.es_operador_tecnico = False
            autor.es_soporte = False
        elif nuevo_rol == 'docente':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = True
            autor.es_externo = False
            autor.es_auxiliar = False
            autor.es_operador_tecnico = False
            autor.es_soporte = False
            autor.institucion_origen = 'UABC'
        elif nuevo_rol == 'externo':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = True
            autor.es_externo = True
            autor.es_auxiliar = False
            autor.es_operador_tecnico = False
            autor.es_soporte = False
            autor.rol_facultad = 'EXT'
            if institucion_externa:
                autor.institucion_origen = institucion_externa
        elif nuevo_rol == 'independiente':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = True
            autor.es_externo = True
            autor.es_auxiliar = False
            autor.es_operador_tecnico = False
            autor.es_soporte = False
            autor.rol_facultad = 'INV_IND'
            if institucion_externa:
                if "independiente" not in institucion_externa.lower():
                    autor.institucion_origen = f"Investigador Independiente ({institucion_externa})"
                else:
                    autor.institucion_origen = institucion_externa
            else:
                autor.institucion_origen = "Investigador Independiente"
            Nombramiento.objects.get_or_create(autor=autor, rol='INV_IND')
        elif nuevo_rol == 'auxiliar':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = False
            autor.es_externo = False
            autor.es_auxiliar = True
            autor.es_operador_tecnico = False
            autor.es_soporte = False
            autor.rol_facultad = 'AUX_INV'
            Nombramiento.objects.get_or_create(autor=autor, rol='AUX_INV')
        elif nuevo_rol == 'operador':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = False
            autor.es_externo = False
            autor.es_auxiliar = False
            autor.es_operador_tecnico = True
            autor.es_soporte = False
            autor.rol_facultad = 'DEP_TEC'
            if not autor.institucion_origen:
                autor.institucion_origen = "FCA UABC - Cómputo y Digitalización"
            Nombramiento.objects.get_or_create(autor=autor, rol='DEP_TEC')
        elif nuevo_rol == 'soporte':
            usuario.is_superuser = False
            usuario.is_staff = True
            autor.es_profesor = False
            autor.es_externo = False
            autor.es_auxiliar = False
            autor.es_operador_tecnico = False
            autor.es_soporte = True
            autor.rol_facultad = 'SOPORTE'
            if not autor.institucion_origen:
                autor.institucion_origen = "FCA UABC - Soporte y Administración"
            Nombramiento.objects.get_or_create(autor=autor, rol='SOPORTE')

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
        titulo_academico = request.POST.get('titulo_academico', '').strip()
        nombres = request.POST.get('nombres', '').strip()
        apellido_paterno = request.POST.get('apellido_paterno', '').strip()
        apellido_materno = request.POST.get('apellido_materno', '').strip()
        nombre = request.POST.get('nombre', '').strip()

        tipo_procedencia = request.POST.get('tipo_procedencia', '').strip() or request.POST.get('procedenciaTipo', '').strip()
        universidad_nombre = request.POST.get('universidad', '').strip()
        siglas = request.POST.get('siglas', '').strip()

        # Armar nombre si no viene explícito
        if not nombre and nombres and apellido_paterno:
            partes = [nombres, apellido_paterno]
            if apellido_materno:
                partes.append(apellido_materno)
            nombre = " ".join(partes).strip()
        elif not nombres and nombre:
            partes = nombre.strip().split()
            prefijos = ['dr.', 'dr', 'dra.', 'dra', 'mtro.', 'mtro', 'mtra.', 'mtra', 'lic.', 'lic', 'ing.', 'ing', 'ph.d.', 'phd']
            if partes and partes[0].lower() in prefijos:
                if not titulo_academico:
                    titulo_academico = partes.pop(0)
                else:
                    partes.pop(0)
            nombres = partes[0] if len(partes) >= 1 else nombre
            apellido_paterno = partes[1] if len(partes) >= 2 else ""
            apellido_materno = " ".join(partes[2:]) if len(partes) >= 3 else ""

        if not nombre:
            return JsonResponse({'success': False, 'error': 'El nombre del autor es obligatorio.'}, status=400)

        # Procedencia
        es_externo = False
        rol_facultad = 'OTRO'
        if tipo_procedencia == 'Independiente':
            institucion = 'Investigador Independiente'
            rol_facultad = 'INV_IND'
            es_externo = False
            tipo_key = 'independiente'
        elif tipo_procedencia == 'Externo' or request.POST.get('es_externo') == 'true':
            es_externo = True
            rol_facultad = 'EXT'
            tipo_key = 'externo'
            if universidad_nombre and siglas:
                Universidad.objects.get_or_create(
                    nombre__iexact=universidad_nombre,
                    defaults={'nombre': universidad_nombre, 'siglas': siglas.upper()}
                )
                institucion = f"{universidad_nombre} ({siglas.upper()})"
            else:
                institucion = request.POST.get('institucion', 'Otra Universidad').strip()
        else:
            institucion = 'UABC'
            rol_facultad = 'PTC'
            es_externo = False
            tipo_key = 'uabc'

        # Verificar si ya existe autor con el mismo nombre e institución para evitar duplicaciones
        autor_existente = Autor.objects.filter(
            nombre__iexact=nombre,
            institucion_origen__iexact=institucion
        ).first()

        if autor_existente:
            if titulo_academico and not autor_existente.titulo_academico:
                autor_existente.titulo_academico = titulo_academico
                autor_existente.save(update_fields=['titulo_academico'])
            return JsonResponse({
                'success': True,
                'id': autor_existente.id,
                'nombre': autor_existente.nombre,
                'nombre_con_titulo': autor_existente.nombre_con_titulo,
                'institucion': autor_existente.institucion_origen,
                'codigo': autor_existente.codigo_institucional,
                'tipo': 'independiente' if (autor_existente.rol_facultad == 'INV_IND' or 'independiente' in (autor_existente.institucion_origen or '').lower()) else ('externo' if autor_existente.es_externo else 'uabc'),
                'ya_existia': True
            })

        nuevo_autor = Autor.objects.create(
            nombre=nombre,
            nombres=nombres,
            apellido_paterno=apellido_paterno,
            apellido_materno=apellido_materno,
            titulo_academico=titulo_academico,
            institucion_origen=institucion,
            rol_facultad=rol_facultad,
            es_profesor=True,
            es_externo=es_externo
        )

        return JsonResponse({
            'success': True,
            'id': nuevo_autor.id,
            'nombre': nuevo_autor.nombre,
            'nombre_con_titulo': nuevo_autor.nombre_con_titulo,
            'institucion': nuevo_autor.institucion_origen,
            'codigo': nuevo_autor.codigo_institucional,
            'tipo': tipo_key
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

    # Métricas detalladas de calidad y estados
    cargados_aprobados = cargados_por_cuenta.filter(estado='aprobado').count()
    cargados_pendientes = cargados_por_cuenta.filter(estado='pendiente').count()
    cargados_rechazados = cargados_por_cuenta.filter(estado='rechazado').count()
    subidas_auto_pendientes_chequeo = cargados_por_cuenta.filter(es_subida_automatica=True, chequeado_por_moderador=False).count()

    # Racha de aprobaciones consecutivas
    estados_obras = list(cargados_por_cuenta.values_list('estado', flat=True))
    racha_actual = 0
    for est in estados_obras:
        if est == 'aprobado':
            racha_actual += 1
        else:
            break
    es_candidato_confianza = (racha_actual >= 10)

    is_trusted = False
    if hasattr(usuario_consultado, 'autor') and usuario_consultado.autor and usuario_consultado.autor.is_trusted_publisher:
        is_trusted = True

    context = {
        'usuario_consultado': usuario_consultado,
        'cargados_por_cuenta': cargados_por_cuenta,
        'asociados_como_autor': asociados_como_autor,
        'total_cargados': cargados_por_cuenta.count(),
        'total_autor': asociados_como_autor.count(),
        'cargados_aprobados': cargados_aprobados,
        'cargados_pendientes': cargados_pendientes,
        'cargados_rechazados': cargados_rechazados,
        'subidas_auto_pendientes_chequeo': subidas_auto_pendientes_chequeo,
        'racha_actual': racha_actual,
        'es_candidato_confianza': es_candidato_confianza,
        'is_trusted': is_trusted,
    }
    return render(request, 'usuario_documentos.html', context)


@user_passes_test(es_superusuario, login_url='/login/')
def asignar_autor_propio_doc_view(request, doc_id, user_id):
    articulo = get_object_or_404(Articulo, id=doc_id)
    usuario = get_object_or_404(User, id=user_id)
    autor = getattr(usuario, 'autor', None)
    if not autor:
        autor, _ = Autor.objects.get_or_create(
            usuario=usuario,
            defaults={'nombre': usuario.get_full_name() or usuario.username, 'correo': usuario.email}
        )
    articulo.autor.add(autor)
    registrar_auditoria(
        request.user,
        "Asignación Rápida de Autor",
        f"Acreditó a {autor.nombre} como autor en la obra: {articulo.titulo}"
    )
    messages.success(request, f'Se acreditó a "{autor.nombre}" en la obra "{articulo.titulo}".')
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('ver_subidas_usuario', user_id=user_id)


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
            try:
                notificar_alerta_cambio_password(usuario)
            except Exception as e:
                logger.warning(f"Error al enviar correo de alerta de cambio de contraseña: {e}")
            registrar_auditoria(request.user, "Restablecimiento de Contraseña",
                                f"Asignó nueva clave al usuario: {usuario.username}")
            messages.success(request, f'La contraseña del usuario "{usuario.username}" ha sido restablecida.')
        else:
            messages.error(request, 'La nueva contraseña no puede estar vacía.')
    return redirect('panel_usuarios')


@user_passes_test(es_superusuario, login_url='/login/')
def impersonar_usuario_view(request, user_id):
    """
    Modo Soporte (Idea 9): Permite al SuperAdmin ingresar de forma segura y explorar el repositorio
    con la vista y permisos exactos de un docente para brindar asistencia técnica.
    """
    target_user = get_object_or_404(User, id=user_id)

    # Protección: no se permite impersonar a otro superusuario
    if target_user.is_superuser and target_user != request.user:
        messages.error(request, "Por seguridad institucional, no es posible explorar la sesión de otro SuperAdministrador.")
        return redirect(f"{reverse('panel_usuarios')}#administrativos")

    original_admin_id = request.user.id
    original_admin_username = request.user.username

    # Iniciar sesión como el usuario objetivo
    login(request, target_user, backend='django.contrib.auth.backends.ModelBackend')

    # Guardar metadatos en la sesión para permitir el retorno
    request.session['impersonator_original_user_id'] = original_admin_id
    request.session['impersonator_original_username'] = original_admin_username

    registrar_auditoria(
        target_user,
        "Inicio Modo Soporte (Impersonation)",
        f"El SuperAdmin {original_admin_username} inició sesión en modo soporte para explorar como {target_user.username}"
    )
    nombre_docente = target_user.get_full_name() or target_user.username
    messages.info(request, f'Has ingresado al Modo Soporte. Estás explorando el repositorio como "{nombre_docente}".')
    return redirect('mi_panel')


@login_required
def dejar_impersonacion_view(request):
    """
    Finaliza el modo soporte y devuelve el control al SuperAdmin original de forma transparente.
    """
    original_admin_id = request.session.get('impersonator_original_user_id')
    if not original_admin_id:
        messages.warning(request, "No te encuentras en modo soporte.")
        return redirect('mi_panel')

    admin_user = get_object_or_404(User, id=original_admin_id)
    docente_consultado = request.user.username

    # Limpiar claves de sesión
    del request.session['impersonator_original_user_id']
    if 'impersonator_original_username' in request.session:
        del request.session['impersonator_original_username']

    # Restaurar la sesión del superadmin
    login(request, admin_user, backend='django.contrib.auth.backends.ModelBackend')

    registrar_auditoria(
        admin_user,
        "Fin Modo Soporte (Impersonation)",
        f"Finalizó la sesión de soporte sobre la cuenta de {docente_consultado} y retornó al panel administrativo"
    )
    messages.success(request, f'Has salido del Modo Soporte. Bienvenido de vuelta a tu sesión administrativa, {admin_user.username}.')
    return redirect(f"{reverse('panel_usuarios')}#administrativos")


@user_passes_test(es_superusuario, login_url='/login/')
def bitacora_usuario_ajax_view(request, user_id):
    """
    Retorna en JSON el historial de actividad y auditoría específico de un usuario
    para la pestaña de Bitácora Individual (Idea 11).
    """
    target_user = get_object_or_404(User, id=user_id)
    
    # Registros donde el usuario fue actor administrativo o sujeto de la auditoría
    filtro_auditoria = Q(admin_usuario=target_user) | Q(detalle__icontains=target_user.username)
    if target_user.get_full_name():
        filtro_auditoria |= Q(detalle__icontains=target_user.get_full_name())
    registros = RegistroAuditoria.objects.filter(filtro_auditoria).order_by('-created_at')[:40]

    # Obras subidas o vinculadas como autor
    obras_qs = Articulo.objects.filter(en_papelera=False)
    if hasattr(target_user, 'autor') and target_user.autor:
        obras_qs = obras_qs.filter(Q(subido_por=target_user) | Q(autor=target_user.autor)).distinct()
    else:
        obras_qs = obras_qs.filter(subido_por=target_user)
    
    obras = obras_qs.order_by('-created_at')[:15]

    lista_reg = [{
        'accion': r.accion,
        'detalle': r.detalle,
        'fecha': r.created_at.strftime('%d/%m/%Y %H:%M'),
    } for r in registros]

    lista_obras = [{
        'id': o.id,
        'titulo': o.titulo,
        'estado': o.get_estado_display() if hasattr(o, 'get_estado_display') else o.estado,
        'fecha': o.created_at.strftime('%d/%m/%Y') if o.created_at else 'N/A'
    } for o in obras]

    return JsonResponse({
        'status': 'ok',
        'user_id': target_user.id,
        'username': target_user.username,
        'nombre': target_user.get_full_name() or target_user.username,
        'fecha_registro': target_user.date_joined.strftime('%d/%m/%Y %H:%M') if target_user.date_joined else 'N/A',
        'ultimo_login': target_user.last_login.strftime('%d/%m/%Y %H:%M') if target_user.last_login else 'Nunca',
        'total_registros': len(lista_reg),
        'registros': lista_reg,
        'total_obras': len(lista_obras),
        'obras': lista_obras
    })