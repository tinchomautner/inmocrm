# Inmocrm — Mini-CRM inmobiliario + portal del cliente

Herramienta para corredores: cargás propiedades (links de Mercado Libre, InfoCasas, etxe, etc.)
para cada cliente, el sistema extrae los datos automáticamente y le genera al cliente un link
personalizado donde marca **Me interesa / No me interesa** y deja comentarios. Vos ves todo en
un panel en vivo.

## Requisitos

- Python 3.10+

## Cómo correrlo localmente

```bash
pip install -r requirements.txt
python app.py
```

Abrís `http://localhost:5000`:

- **`/`** — panel del corredor: crear clientes, pegar links, ver respuestas.
- **`/p/<cliente>`** — portal que se le envía al cliente.

La base de datos (`inmocrm.db`) se crea sola la primera vez.

## Estructura

```
app.py           # rutas Flask
db.py            # base de datos SQLite
scraper.py       # extracción de datos desde los links
templates/       # admin.html, client_detail.html, portal.html
static/          # estilos + logos
```

## Configuración

En `app.py`:

- `ADVISOR_NAME` / `ADVISOR_WHATSAPP` — nombre y WhatsApp del asesor al que el cliente
  le avisa cuando finaliza su selección.

## Variables de entorno (en el host)

- `DATABASE_URL` — conexión Postgres (ej. Neon) para que los datos persistan. Si no se define,
  usa SQLite local.
- `ADMIN_PASSWORD` — contraseña del panel del corredor. **Definirla sí o sí en producción**
  (el default `etxe2026` es público en el repo).
- `SECRET_KEY` — texto aleatorio largo para firmar las sesiones de login.
- `NOTIFY_WHATSAPP` — número del corredor (sin `+`, con código país) que recibe la notificación
  cuando un cliente finaliza su selección. Si no se define, usa `ADVISOR_WHATSAPP`.
- `CALLMEBOT_APIKEY` — apikey del bot de WhatsApp (https://www.callmebot.com/blog/free-api-whatsapp-messages/).
  Sin esto, la notificación queda en silencio (igual el badge en el panel sigue funcionando).

## Publicarlo online (para que los clientes abran el link)

GitHub Pages **no** sirve (solo archivos estáticos; esto necesita Python). Se hostea en
**Render** (gratis) con base **Neon** (Postgres gratis y persistente), y un ping cada 10 min
desde **cron-job.org** para que no se duerma. Ver la guía paso a paso aparte.

## Notas

- El precio se extrae de datos estructurados (JSON-LD, incluidos rangos de proyectos) y del
  texto, con doble User-Agent (incluye Mercado Libre). **etxe** carga el precio por JavaScript:
  ahí se completa a mano con "Editar datos".
- Botón **↻ Actualizar** (por propiedad o por cliente): re-extrae y rellena datos faltantes
  sin pisar lo editado a mano.
