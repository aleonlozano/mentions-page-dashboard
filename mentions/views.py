import os
import requests
from requests.exceptions import ReadTimeout, RequestException
from django.conf import settings
from django.http import JsonResponse, HttpResponseServerError, HttpResponse
import urllib.parse
from django.shortcuts import render, redirect
from datetime import datetime, timezone
import math
GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


def _fetch_tagged_posts(limit=10):
    """
    Obtiene publicaciones de Facebook donde la página ha sido etiquetada.
    Usa FB_PAGE_ID y FB_PAGE_ACCESS_TOKEN de settings.
    """
    page_id = getattr(settings, "FB_PAGE_ID", None)
    access_token = getattr(settings, "FB_PAGE_ACCESS_TOKEN", None)

    if not page_id or not access_token:
        return []

    url = f"{GRAPH_API_BASE}/{page_id}/tagged"
    params = {
        "access_token": access_token,
        "fields": ",".join(
            [
                "id",
                "from",
                "message",
                "created_time",
                "permalink_url",
            ]
        ),
        "limit": limit,
    }

    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("data", [])


def _fetch_instagram_tagged(limit=50):
    ig_user_id = getattr(settings, "IG_USER_ID", None)
    access_token = getattr(settings, "FB_PAGE_ACCESS_TOKEN", None)

    if not ig_user_id or not access_token:
        return []

    url = f"{GRAPH_API_BASE}/{ig_user_id}/tags"
    params = {
        "access_token": access_token,
        "fields": "id,caption,username,timestamp,permalink",
        "limit": limit,
    }

    resp = requests.get(url, params=params, timeout=10)

    try:
        data = resp.json()
    except ValueError:
        resp.raise_for_status()
        return []

    # Si Meta devuelve error (#10), lo tratamos como "IG no disponible"
    if "error" in data:
        err = data["error"]
        msg = err.get("message", "")
        code = err.get("code")
        if code == 10:
            # Logueas si quieres, pero no rompes el panel
            return []
        # Otros errores sí los lanzas
        raise Exception(f"Instagram API error: {msg} (code {code})")

    resp.raise_for_status()
    return data.get("data", [])

def _analyze_sentiment(text):
    """
    Análisis de sentimiento muy sencillo basado en palabras clave.
    Devuelve un dict con label: positive|neutral|negative y score (0..1).
    """
    if not text:
        return {"label": "neutral", "score": 0.0}

    text_l = text.lower()

    positive_words = [
        "bueno",
        "genial",
        "excelente",
        "maravilloso",
        "gracias",
        "felicitaciones",
        "recomendado",
        "me gusta",
        "buenísimo",
        "increíble",
    ]
    negative_words = [
        "malo",
        "pésimo",
        "horrible",
        "terrible",
        "queja",
        "reclamo",
        "no me gusta",
        "decepción",
        "fraude",
        "estafa",
    ]

    pos_count = sum(1 for w in positive_words if w in text_l)
    neg_count = sum(1 for w in negative_words if w in text_l)

    if pos_count > neg_count:
        label = "positive"
        score = min(1.0, pos_count / (pos_count + neg_count or 1))
    elif neg_count > pos_count:
        label = "negative"
        score = min(1.0, neg_count / (pos_count + neg_count or 1))
    else:
        label = "neutral"
        score = 0.0

    return {"label": label, "score": score}


def _compute_impact(post_dict):
    """
    Cálculo heurístico de impacto basado en longitud del mensaje y recencia.
    Espera un dict con al menos message y created_time.
    """
    message = (post_dict.get("message") or "") if isinstance(post_dict, dict) else ""
    created_time = post_dict.get("created_time") if isinstance(post_dict, dict) else None

    length_score = min(len(message) / 280.0, 1.0) if message else 0.0

    recency_score = 0.0
    if created_time:
        try:
            if isinstance(created_time, str):
                # created_time tipo ISO 8601 de Facebook/Instagram
                dt = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
            else:
                dt = created_time
            now = datetime.now(timezone.utc)
            days_diff = (now - dt).days
            # Entre 0 y 30 días max, más reciente => mayor score
            recency_score = max(0.0, 1.0 - min(days_diff, 30) / 30.0)
        except Exception:
            recency_score = 0.0

    impact_score = round(0.6 * recency_score + 0.4 * length_score, 3)

    if impact_score >= 0.66:
        level = "alto"
    elif impact_score >= 0.33:
        level = "medio"
    else:
        level = "bajo"

    return {
        "impact_score": impact_score,
        "impact_level": level,
    }
def mentions_api(request):
    """
    API de menciones con filtrado, orden y paginación en el servidor.

    Parámetros de query opcionales:
      - sentiment: all | positive | neutral | negative
      - search: texto libre para buscar en message / from_name
      - sort_field: created_time | from_name | sentiment | impact
      - sort_dir: asc | desc
      - page: número de página (1-based)
      - page_size: tamaño de página (por defecto 10)
      - network: all | facebook | instagram
    """
    # Filtro por red: all | facebook | instagram
    network_filter = request.GET.get("network", "all")
    if network_filter not in ("all", "facebook", "instagram"):
        network_filter = "all"

    # Obtener posts de Facebook e Instagram según el filtro de red
    try:
        raw_sources = []

        if network_filter in ("all", "facebook"):
            fb_posts = _fetch_tagged_posts(limit=39)
            raw_sources.extend([("facebook", p) for p in fb_posts])

        if network_filter in ("all", "instagram"):
            ig_posts = _fetch_instagram_tagged(limit=39
                                               )
            raw_sources.extend([("instagram", p) for p in ig_posts])

    except ReadTimeout as e:
        return JsonResponse(
            {
                "error": "Error al consultar la API de Facebook",
                "detail": f"Tiempo de espera agotado al llamar a Facebook/Instagram: {e}",
            },
            status=504,
        )
    except Exception as e:
        return JsonResponse(
            {
                "error": "Error al consultar la API de Facebook/Instagram",
                "detail": str(e),
            },
            status=500,
        )

    mentions = []

    # Normalizar estructura de menciones y calcular impacto
    for source, p in raw_sources:
        if source == "facebook":
            message = p.get("message")
            created_time = p.get("created_time")
            permalink_url = p.get("permalink_url", "")
            from_obj = p.get("from") or {}
            from_name = from_obj.get("name", "")
            from_id = from_obj.get("id", "")
        else:  # instagram
            message = p.get("caption")
            created_time = p.get("timestamp")
            permalink_url = p.get("permalink", "")
            from_name = p.get("username", "")
            from_id = ""

        sentiment = _analyze_sentiment(message)
        stats = _compute_impact(
            {
                "message": message,
                "created_time": created_time,
            }
        )

        mentions.append(
            {
                "id": p.get("id"),
                "network": source,  # "facebook" o "instagram"
                "from_name": from_name,
                "from_id": from_id,
                "message": message,
                "created_time": created_time,
                "permalink_url": permalink_url,
                "sentiment": sentiment,
                "stats": stats,
            }
        )

    # Parámetros de filtrado/orden/paginación
    sentiment_filter = request.GET.get("sentiment", "all")
    search_q = (request.GET.get("search") or "").strip().lower()
    sort_field = request.GET.get("sort_field", "created_time")
    sort_dir = request.GET.get("sort_dir", "desc")
    try:
        page = int(request.GET.get("page", "1"))
    except ValueError:
        page = 1
    try:
        page_size = int(request.GET.get("page_size", "10"))
    except ValueError:
        page_size = 10
    page = max(1, page)
    page_size = max(1, min(page_size, 100))

    # Filtrado
    filtered = []
    for m in mentions:
        if sentiment_filter != "all" and m["sentiment"]["label"] != sentiment_filter:
            continue
        if search_q:
            text = (m.get("message") or "").lower()
            from_name = (m.get("from_name") or "").lower()
            if search_q not in text and search_q not in from_name:
                continue
        filtered.append(m)

    # Recalcular contadores de sentimiento sobre el conjunto filtrado
    positive_count = neutral_count = negative_count = 0
    for m in filtered:
        label = m["sentiment"]["label"]
        if label == "positive":
            positive_count += 1
        elif label == "negative":
            negative_count += 1
        else:
            neutral_count += 1

    # Orden
    sentiment_order = {"negative": 0, "neutral": 1, "positive": 2}

    def sort_key(m):
        if sort_field == "created_time":
            return m.get("created_time") or ""
        elif sort_field == "from_name":
            return (m.get("from_name") or "").lower()
        elif sort_field == "sentiment":
            return sentiment_order.get(m["sentiment"]["label"], 1)
        elif sort_field == "impact":
            return float(m.get("stats", {}).get("impact_score") or 0.0)
        return m.get("created_time") or ""

    reverse = sort_dir == "desc"
    filtered.sort(key=sort_key, reverse=reverse)

    # Paginación
    total_items = len(filtered)
    if total_items:
        total_pages = max(1, math.ceil(total_items / page_size))
    else:
        total_pages = 1

    if page > total_pages:
        page = total_pages

    start = (page - 1) * page_size
    end = start + page_size
    page_items = filtered[start:end]

    summary = {
        "total_mentions": total_items,
        "positive": positive_count,
        "neutral": neutral_count,
        "negative": negative_count,
    }

    return JsonResponse(
        {
            "mentions": page_items,
            "summary": summary,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_items": total_items,
                "total_pages": total_pages,
            },
        }
    )


def dashboard(request):
    """
    Vista principal del panel de menciones.
    Renderiza la plantilla del dashboard pasando información básica
    de la página/red que se está monitoreando y, si existe,
    el perfil de Instagram conectado almacenado en sesión.
    """
    ig_profile = request.session.get("ig_profile")
    context = {
        "page_name": getattr(settings, "FB_PAGE_NAME", "Noticias del Meta"),
        "page_id": getattr(settings, "FB_PAGE_ID", ""),
        "ig_profile": ig_profile,
    }
    return render(request, "mentions/dashboard.html", context)


# Nuevas vistas para conectar Instagram
from django.shortcuts import redirect

def connect_instagram(request):
    """
    Redirige al diálogo OAuth de Meta para conectar una cuenta de Instagram profesional.
    Esta vista se usa desde el botón "Conectar Instagram" en el dashboard.
    """
    client_id = getattr(settings, "META_APP_ID", None)
    if not client_id:
        return HttpResponse(
            "META_APP_ID no está configurado en settings. Añádelo a tu .env/settings.py.",
            status=500,
        )

    redirect_uri = "http://localhost:8000/instagram/callback/"
    scope = [
        "instagram_basic",
        "pages_show_list",
        "pages_read_engagement",
        "pages_read_user_content",
    ]
    # Para producción deberías generar un state aleatorio y guardarlo en sesión
    state = "simple-state"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": ",".join(scope),
        "response_type": "code",
        "state": state,
    }

    url = "https://www.facebook.com/v21.0/dialog/oauth?" + urllib.parse.urlencode(params)
    return redirect(url)


def instagram_callback(request):
    """
    Recibe el `code` de Meta, intercambia por un access_token de usuario
    y obtiene el perfil de la cuenta de Instagram profesional conectada.
    Guarda un resumen del perfil en la sesión y redirige al dashboard.
    Esta vista sirve para el flujo de App Review.
    """
    error = request.GET.get("error")
    if error:
        return HttpResponse(f"Error en OAuth: {error}", status=400)

    code = request.GET.get("code")
    if not code:
        return HttpResponse("Falta el parámetro 'code' en la respuesta de OAuth.", status=400)

    client_id = getattr(settings, "META_APP_ID", None)
    client_secret = getattr(settings, "META_APP_SECRET", None)
    if not client_id or not client_secret:
        return HttpResponse(
            "META_APP_ID o META_APP_SECRET no están configurados en settings.",
            status=500,
        )

    redirect_uri = "http://localhost:8000/instagram/callback/"

    # 1) Intercambiar code por access_token de usuario
    try:
        token_resp = requests.get(
            "https://graph.facebook.com/v21.0/oauth/access_token",
            params={
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "client_secret": client_secret,
                "code": code,
            },
            timeout=15,
        )
        token_data = token_resp.json()
    except Exception as e:
        return HttpResponse(f"Error al obtener access_token: {e}", status=500)

    user_access_token = token_data.get("access_token")
    if not user_access_token:
        return HttpResponse(f"Respuesta inesperada al obtener access_token: {token_data}", status=500)

    # 2) Obtener páginas administradas por el usuario
    try:
        pages_resp = requests.get(
            "https://graph.facebook.com/v21.0/me/accounts",
            params={"access_token": user_access_token},
            timeout=15,
        )
        pages_data = pages_resp.json()
    except Exception as e:
        return HttpResponse(f"Error al obtener las páginas administradas: {e}", status=500)

    ig_id = None
    # Buscamos la primera página que tenga una cuenta de Instagram conectada
    for p in pages_data.get("data", []):
        page_id = p.get("id")
        if not page_id:
            continue
        try:
            detail_resp = requests.get(
                f"{GRAPH_API_BASE}/{page_id}",
                params={
                    "access_token": user_access_token,
                    "fields": "name,connected_instagram_account",
                },
                timeout=15,
            )
            detail = detail_resp.json()
        except Exception:
            continue

        if "connected_instagram_account" in detail:
            ig_account = detail.get("connected_instagram_account") or {}
            ig_id = ig_account.get("id")
            break

    if not ig_id:
        return HttpResponse(
            "No se encontró ninguna página con una cuenta de Instagram profesional conectada.",
            status=400,
        )

    # 3) Obtener perfil de la cuenta de Instagram profesional
    try:
        ig_resp = requests.get(
            f"{GRAPH_API_BASE}/{ig_id}",
            params={
                "access_token": user_access_token,
                "fields": "id,username,biography,profile_picture_url",
            },
            timeout=15,
        )
        ig_profile = ig_resp.json()
    except Exception as e:
        return HttpResponse(f"Error al obtener el perfil de Instagram: {e}", status=500)

    # 4) Guardar perfil simplificado en sesión para usarlo en el dashboard y para App Review
    request.session["ig_profile"] = {
        "id": ig_profile.get("id"),
        "username": ig_profile.get("username"),
        "biography": ig_profile.get("biography"),
        "profile_picture_url": ig_profile.get("profile_picture_url"),
    }

    # (Opcional) aquí podrías guardar ig_id / tokens en BD para usarlos luego en las llamadas
    # de menciones de Instagram. Para App Review basta con mostrar el perfil.

    return redirect("dashboard")

def disconnect_instagram(request):
    """
    Elimina la información de la cuenta de Instagram conectada de la sesión
    y vuelve al dashboard.
    """
    request.session.pop("ig_profile", None)
    # Si en el futuro guardas tokens/ig_id en sesión o BD,
    # aquí también podrías limpiarlos.
    return redirect("dashboard")
