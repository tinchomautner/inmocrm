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

## Publicarlo online (para que los clientes abran el link)

GitHub Pages **no** sirve para esta app (Pages solo aloja archivos estáticos; esto necesita
Python corriendo). Hay que usar un host de Python. La forma más simple:

### Render (gratis)

1. Crear cuenta en https://render.com y conectarla con tu GitHub.
2. **New → Blueprint** y elegir este repo. Render lee `render.yaml` y configura todo solo.
   (Alternativa: **New → Web Service**, build `pip install -r requirements.txt`,
   start `gunicorn app:app --bind 0.0.0.0:$PORT`.)
3. Te queda una URL pública tipo `https://inmocrm.onrender.com`. Ese es el panel; el link
   del cliente es `https://inmocrm.onrender.com/p/<cliente>`.

> Nota: en el plan free de Render el disco es efímero — si redeployás, la base `inmocrm.db`
> se reinicia. Para datos permanentes, agregar un disco persistente (de pago) o usar
> PythonAnywhere (free, almacenamiento persistente).

## Notas

- Mercado Libre y etxe cargan el precio por JavaScript; en esos casos el precio queda vacío
  y se completa a mano con "Editar datos" en el panel. El resto (foto, título, dormitorios) se extrae solo.
