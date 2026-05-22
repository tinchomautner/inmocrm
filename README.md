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

## Notas

- Mercado Libre y etxe cargan el precio por JavaScript; en esos casos el precio queda vacío
  y se completa a mano con "Editar datos" en el panel. El resto (foto, título, dormitorios) se extrae solo.
- Para publicarlo online no alcanza GitHub Pages (es una app con backend). Usar un host de
  Python: Render, Railway o PythonAnywhere (todos con plan gratuito).
