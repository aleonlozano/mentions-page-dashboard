# Panel de monitoreo de menciones en Facebook, Instagram y X

Este proyecto es un **panel web interactivo**, que permite monitorear en tiempo real las publicaciones de Facebook (y opcionalmente Instagram) que **mencionan o etiquetan** una página específica.

El panel está pensado para páginas o marcas que quieren:

- Ver rápidamente **qué publicaciones las mencionan**.
- Tener una **clasificación de sentimiento** (positivo / neutral / negativo).
- Ver un **indicador de impacto** (heurístico) por publicación.
- Filtrar, ordenar y paginar de forma cómoda desde un único dashboard.

> ⚠️ **Nota importante sobre Instagram:**  
> El soporte de Instagram usa el endpoint `/IG_USER_ID/tags` del Instagram Graph API. Meta suele restringir este endpoint con el error `(#10) Application does not have permission for this action`, incluso para administradores, si la app no ha pasado por **App Review** o no tiene permisos avanzados.  
> El proyecto maneja este caso de forma segura (no rompe el panel), pero es posible que en tu app **no veas datos de Instagram hasta completar ese proceso con Meta**.


---

## 1. Requisitos

### Versión de Python y Django

- **Python**: 3.11 (recomendado)  
- **Django**: 5.x (se instala desde `requirements.txt`)

### Dependencias principales

Las dependencias se instalan automáticamente desde `requirements.txt`, pero a nivel conceptual el proyecto usa:

- `Django` – framework web.
- `requests` – para llamar a la API de Facebook / Instagram.
- `python-dotenv` o similar (según requirements) – para leer variables de entorno desde `.env`.

### Cuenta de Facebook / Instagram

Para que el panel pueda obtener datos reales, necesitas:

1. Una **Página de Facebook**.
2. Una **Facebook App** en [Meta for Developers](https://developers.facebook.com/).
3. Un **Page Access Token** válido para esa página, generado con tu app.
4. (Opcional) Una **cuenta de Instagram Business / Creator** conectada a la página, y su **IG User ID**.

---

## 2. Estructura del proyecto

La estructura base del repo luce aproximadamente así:

```text
fb_mentions_django/
├─ fb_mentions_dashboard/        # Proyecto Django (settings, urls, wsgi)
├─ mentions/                     # App principal del panel
│  ├─ templates/
│  │  └─ mentions/
│  │     └─ dashboard.html       # Interfaz del panel
│  ├─ static/mentions/           # CSS/JS adicionales (si aplica)
│  ├─ views.py                   # Lógica del API + dashboard
│  ├─ urls.py                    # Rutas propias de la app
│  └─ __init__.py
├─ manage.py
├─ requirements.txt
├─ .env                          # Variables de entorno (NO subir a git)
└─ README.md                     # Este archivo
```

> La estructura exacta puede variar ligeramente, pero la app principal se llama `mentions` y el proyecto raíz `fb_mentions_dashboard`.


---

## 3. Configuración de entorno

El proyecto lee las variables desde un archivo `.env` en la raíz del repo.

Ejemplo de `.env`:

```env
# ID de la Página de Facebook
FB_PAGE_ID=xxxxxxxxxxxx

# Page Access Token generado con tu app de Meta
FB_PAGE_ACCESS_TOKEN=EAAXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# Nombre de la página (se muestra en el header del panel)
FB_PAGE_NAME=xxxxx

# Versión de la Graph API que quieres usar
FB_GRAPH_VERSION=v24.0

# Modo debug de Django
DEBUG=True

# Credenciales de la app de Meta
META_APP_ID=1234567890123xx
META_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Cómo obtener estos valores

#### FB_PAGE_ID

1. Ve a tu página de Facebook.
2. En “Información de la página” o desde el Graph Explorer con:  
   `/{page-username}?fields=id`
3. Copia el `id`.

#### FB_PAGE_ACCESS_TOKEN (Page Access Token)

1. Ve al **Graph API Explorer** en Meta Developers.
2. Elige tu **App**.
3. Genera un **User Access Token** marcando al menos estos permisos:
   - `pages_show_list`
   - `pages_read_engagement`
   - `pages_read_user_content`
   - `read_insights` (opcional, si quieres métricas)
   - `instagram_basic` (para Instagram)
4. En el mismo Graph Explorer, usa la opción para obtener el **Page Access Token** de tu Página (Noticias del Meta u otra).
5. Copia ese token en `FB_PAGE_ACCESS_TOKEN`.

> ⚠️ Este token puede expirar en cierto tiempo. Para producción, se recomienda generar **tokens de larga duración** y manejar la renovación automática.

> Nota: Además, las variables `META_APP_ID` y `META_APP_SECRET` también se leen desde el `.env` para flujos de autenticación avanzados, pero **nunca** se deben commitear con sus valores reales.

---

## 4. Instalación y ejecución en local

### 4.1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/fb_mentions_django.git
cd fb_mentions_django
```

### 4.2. Crear y activar entorno virtual

Con Python 3.11:

```bash
python -m venv .venv
source .venv/bin/activate  # En macOS / Linux
source .venv\Scripts\activate   # En Windows
```

Verifica que usas la versión correcta:

```bash
python --version
```

### 4.3. Instalar dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.4. Configurar `.env`

Crea un archivo `.env` en la raíz (o copia desde `.env.example` si existe) y rellena:

- `FB_PAGE_ID`
- `FB_PAGE_ACCESS_TOKEN`
- `FB_PAGE_NAME`
- `FB_GRAPH_VERSION`
- `DEBUG`

### 4.5. Migraciones de Django

```bash
python manage.py migrate
```

### 4.6. Ejecutar el servidor de desarrollo

```bash
python manage.py runserver
```

Luego abre en el navegador:

- Panel: `http://127.0.0.1:8000/`
- API JSON: `http://127.0.0.1:8000/api/mentions/`


---

## 5. Funcionalidades del panel

### 5.1. Vista principal (`/`)

Renderiza el template `mentions/dashboard.html`, que incluye:

- Encabezado con:
  - Nombre de la página (`FB_PAGE_NAME`).
  - Resumen rápido de métricas.
- Tarjetas de resumen:
  - Total de menciones.
  - Conteo de positivas, neutrales y negativas.
- Barra de filtros:
  - **Búsqueda** por texto (en el mensaje o nombre de quien publica).
  - Filtro por **sentimiento** (todos, positivo, neutral, negativo).
  - Filtro por **red** (todas, solo Facebook, solo Instagram).
  - Orden por fecha, origen, sentimiento, impacto.
- Tabla de resultados:
  - Origen (nombre de la página/usuario que te menciona).
  - Fecha de la publicación.
  - Extracto del mensaje.
  - Etiqueta de sentimiento.
  - “Nivel de impacto” (bajo, medio, alto).
  - Link a la publicación original.
- Paginación:
  - Botones **Anterior / Siguiente**.
  - Indicador de página actual.
  - **Botón “Ver todos”** para cargar todo en una sola página y **“Ver paginado”** para volver a 10 por página.

La interfaz está construida con **HTML + clases tipo TailwindCSS (vía CDN)** y **JavaScript vanilla** para llamar al endpoint `/api/mentions/` y renderizar la tabla dinámicamente.

### 5.2. Endpoint de API (`/api/mentions/`)

La vista `mentions_api` expone un JSON con este formato:

```json
{
  "mentions": [
    {
      "id": "1234567890",
      "network": "facebook",
      "from_name": "Página que menciona",
      "from_id": "1122334455",
      "message": "Texto de la publicación...",
      "created_time": "2025-10-07T00:38:28+0000",
      "permalink_url": "https://www.facebook.com/...",
      "sentiment": {
        "label": "positive",
        "score": 0.75
      },
      "stats": {
        "impact_score": 0.82,
        "impact_level": "alto"
      }
    }
  ],
  "summary": {
    "total_mentions": 39,
    "positive": 10,
    "neutral": 20,
    "negative": 9
  },
  "pagination": {
    "page": 1,
    "page_size": 10,
    "total_items": 39,
    "total_pages": 4
  }
}
```

#### Parámetros de query soportados

- `network`:
  - `all` (por defecto)
  - `facebook`
  - `instagram`

- `sentiment`:
  - `all` (por defecto)
  - `positive`
  - `neutral`
  - `negative`

- `search`:
  - Texto libre para buscar en `message` o `from_name`.

- `sort_field`:
  - `created_time`
  - `from_name`
  - `sentiment`
  - `impact`

- `sort_dir`:
  - `asc`
  - `desc` (por defecto)

- `page`:
  - Número de página (1 por defecto).

- `page_size`:
  - Tamaño de página (por defecto 10, limitado a máximo 100).
  - El front lo usa para cambiar entre modo paginado y “Ver todos”.

Ejemplo:

```http
GET /api/mentions/?network=facebook&sentiment=positive&search=granada&sort_field=impact&sort_dir=desc&page=1&page_size=10
```


---

## 6. Lógica interna: cómo se obtienen y procesan las menciones

### 6.1. Facebook – `_fetch_tagged_posts`

Se consulta el endpoint:

```http
GET /{FB_PAGE_ID}/tagged
```

con campos:

- `id`
- `from`
- `message`
- `created_time`
- `permalink_url`

Se usa el `FB_PAGE_ACCESS_TOKEN` y la versión indicada en `FB_GRAPH_VERSION`.

### 6.2. Instagram – `_fetch_instagram_tagged` (opcional)

Se consulta el endpoint:

```http
GET /{IG_USER_ID}/tags
```

con campos:

- `id`
- `caption`
- `username`
- `timestamp`
- `permalink`

> ⚠️ Debes tener en cuenta que este endpoint está fuertemente controlado por Meta.  
> Es habitual obtener:
> ```json
> {
>   "error": {
>     "message": "(#10) Application does not have permission for this action",
>     "type": "OAuthException",
>     "code": 10
>   }
> }
> ```
> aunque seas administrador, mientras la app no haya pasado por **App Review** con los permisos/funciones adecuados.  
> El proyecto está preparado para **atrapar este error y devolver una lista vacía** de IG, de modo que el panel no se rompa.

### 6.3. Análisis de sentimiento – `_analyze_sentiment(text)`

Se implementa un análisis de sentimiento **simple basado en palabras clave en español**, por ejemplo:

- Positivas: `bueno`, `genial`, `excelente`, `maravilloso`, `gracias`, `felicitaciones`, `recomendado`, `me gusta`, etc.
- Negativas: `malo`, `pésimo`, `horrible`, `terrible`, `queja`, `reclamo`, `no me gusta`, `decepción`, `fraude`, `estafa`, etc.

Regresa un dict:

```python
{"label": "positive" | "neutral" | "negative", "score": float}
```

Este enfoque es deliberadamente simple, pensado para ser fácil de entender y extender. En un futuro podrías reemplazarlo por un modelo de ML o llamadas a un servicio de IA.

### 6.4. Impacto – `_compute_impact(post_dict)`

Calcula un **impacto heurístico** combinando:

- **Longitud del mensaje** (normalizada sobre ~280 caracteres).
- **Recencia** (días desde la publicación, con máximo de 30 días para puntuar).

Devuelve:

```
{
  "impact_score": 0.0–1.0,
  "impact_level": "bajo" | "medio" | "alto",
}
```

Este valor se usa para:

- Ordenar por “impacto”.
- Mostrar visualmente el “nivel de impacto” en la tabla.

---
