# Instalación desde cero — Guía para alguien sin experiencia

Hola 👋 Esta guía te lleva paso a paso para poder **usar y editar** este proyecto en tu
computadora, aunque nunca hayas programado. Seguí los pasos EN ORDEN, sin saltarte ninguno.
Tomate tu tiempo. Si un paso falla, mirá la sección "Si algo no funciona" al final.

> Vas a instalar 4 cosas: una **cuenta de GitHub**, el programa **Git**, **Python** y **Codex**.
> Suena mucho, pero cada una es "siguiente, siguiente, listo".

---

## ⭐ ANTES DE EMPEZAR — dos formas de usar esto

Hay **dos cosas distintas** que podés hacer, y necesitan cosas diferentes:

- **A) USAR la app** (cargar clientes, pegar links de propiedades, ver respuestas):
  esto NO necesita instalar NADA. Solo entrás a una página web con un usuario y contraseña.
  👉 Ver la sección **"USAR LA APP"** al final. Si por ahora solo querés usarla, andá directo ahí.

- **B) EDITAR la app** (cambiar cómo funciona, agregar cosas con Codex):
  para esto sí hay que instalar los programas. Es el resto de esta guía.

---

## Paso 1 — Crear tu cuenta de GitHub (5 minutos)

GitHub es donde vive el código del proyecto.

1. Entrá a **https://github.com** → botón **Sign up** (registrarse).
2. Poné tu email, una contraseña y un nombre de usuario. Anotá el usuario y la contraseña.
3. Confirmá tu email (te llega un correo).
4. **Avisale a tu novio tu usuario de GitHub.** Él te va a agregar al proyecto (te llega una
   invitación por mail; abrila y aceptá — botón verde "Accept invitation").

Sin este paso, no vas a poder bajar el proyecto. Esperá a aceptar la invitación antes de seguir.

---

## Paso 2 — Instalar Git

Git es el programa que baja y sube los cambios del proyecto.

### Si tenés Windows
1. Entrá a **https://git-scm.com/download/win** → se descarga solo el instalador.
2. Abrí el archivo descargado → **Next, Next, Next...** hasta **Install** (dejá todo por defecto).
3. Al terminar, **Finish**.

### Si tenés Mac
1. Abrí el programa **Terminal** (buscalo con la lupa 🔍 arriba a la derecha, escribí "Terminal").
2. Escribí esto y Enter: `git --version`
3. Si no lo tenés, Mac te ofrece instalarlo solo (botón "Instalar"). Aceptá.

Para saber si quedó: abrí la Terminal (Mac) o **Git Bash** (Windows, buscalo en el menú inicio)
y escribí `git --version`. Si aparece un número de versión, ✅ listo.

---

## Paso 3 — Instalar Python

Python es lo que hace funcionar la app.

### Windows
1. Entrá a **https://www.python.org/downloads** → botón grande **Download Python**.
2. Abrí el instalador. **MUY IMPORTANTE:** antes de instalar, tildá abajo la casilla
   **"Add python.exe to PATH"** ✅ (si no la tildás, después no funciona).
3. **Install Now** → esperá → **Close**.

### Mac
1. Entrá a **https://www.python.org/downloads** → **Download Python** → abrí el instalador →
   siguiente, siguiente, listo.

Para saber si quedó: en la Terminal/Git Bash escribí `python --version` (en Mac quizás sea
`python3 --version`). Si aparece un número, ✅ listo.

---

## Paso 4 — Instalar Codex

Codex es el asistente que edita el código por vos cuando le explicás qué querés.

Codex necesita otro programa llamado **Node.js**. Instalalo primero:

1. Entrá a **https://nodejs.org** → descargá la versión que dice **LTS** → instalá
   (siguiente, siguiente, listo).
2. Ahora abrí la Terminal (Mac) o **Git Bash** (Windows) y escribí:
   ```
   npm install -g @openai/codex
   ```
   Esperá a que termine (tarda un minuto).
3. Para usar Codex necesitás una cuenta de **ChatGPT** (con un plan que incluya Codex, como
   ChatGPT Plus). La primera vez que abras Codex te va a pedir iniciar sesión con esa cuenta.

> Si tu Codex es otro programa distinto a este, saltá este paso e instalá el que uses. Lo demás
> de la guía sirve igual.

---

## Paso 5 — Bajar el proyecto a tu compu

1. Abrí la Terminal (Mac) o **Git Bash** (Windows).
2. Vamos a ponerlo en tu carpeta de Documentos. Escribí (una línea, Enter):
   ```
   cd ~/Documents
   ```
3. Ahora bajá el proyecto (Enter):
   ```
   git clone https://github.com/tinchomautner/inmocrm.git
   ```
   La primera vez te puede pedir tu usuario y contraseña de GitHub.
4. Entrá a la carpeta del proyecto:
   ```
   cd inmocrm
   ```
5. Instalá lo que necesita la app (una sola vez):
   ```
   pip install -r requirements.txt
   ```
   (En Mac, si `pip` no anda, probá `pip3`.)

✅ Ya tenés todo el proyecto en tu compu.

---

## Paso 6 — Abrir Codex y editar

1. Parada en la carpeta del proyecto (después del Paso 5 ya estás ahí), escribí:
   ```
   codex
   ```
2. Se abre el asistente. **Lo primero que le tenés que decir**, copiá y pegá esto:
   > Leé el archivo PARA_DESARROLLADORA.md para entender el proyecto antes de hacer cambios.
3. Ahora pedile lo que quieras **en español normal**, por ejemplo:
   > Quiero que en el portal del cliente el botón de "Me interesa" sea más grande.
4. Codex hace los cambios. Para ver cómo quedó antes de publicar, probá la app local (Paso 7).

---

## Paso 7 — Probar los cambios en tu compu (antes de publicar)

1. En la Terminal/Git Bash, dentro de la carpeta `inmocrm`, escribí:
   ```
   python app.py
   ```
   (En Mac quizás `python3 app.py`.)
2. Abrí el navegador en **http://localhost:5000**. Esa es la app corriendo en TU compu, con
   datos de prueba tuyos (NO toca los datos reales). Probá tranquila.
3. Para apagarla: volvé a la Terminal y apretá **Ctrl + C**.

---

## Paso 8 — Publicar los cambios (que aparezcan online de verdad)

Cuando estés conforme:

1. En la Terminal/Git Bash, dentro de `inmocrm`, escribí estas tres líneas (una por vez, Enter):
   ```
   git add -A
   git commit -m "describí acá qué cambiaste"
   git push
   ```
2. Listo. En 1 o 2 minutos los cambios aparecen solos en **https://inmocrm.onrender.com**.

> Consejo: antes de un cambio grande, entrá a la app → `/admin/estado` → **Descargar backup**,
> así tenés una copia de los datos por las dudas.

---

## 🔄 Para seguir trabajando otro día

No hace falta reinstalar nada. Solo:
1. Abrí la Terminal/Git Bash → `cd ~/Documents/inmocrm`
2. Bajá lo último (por si tu novio cambió algo): `git pull`
3. Abrí Codex: `codex` — o probá la app: `python app.py`

---

## 🖥️ USAR LA APP (sin instalar nada)

Para el uso diario (cargar clientes y propiedades) NO necesitás nada de lo de arriba:

1. Entrá a **https://inmocrm.onrender.com**
2. Poné la contraseña (pedísela a tu novio).
3. Creás clientes, pegás links de propiedades, y a cada cliente le copiás su link
   (`https://inmocrm.onrender.com/p/nombre`) para mandárselo por WhatsApp.

La primera vez del día puede tardar ~1 minuto en abrir (la app estaba "dormida"). Después va rápido.

---

## ❓ Si algo no funciona

- **"git no se reconoce" / "python no se reconoce" (Windows):** cerrá y volvé a abrir Git Bash.
  Si sigue, reinstalá ese programa y en Python acordate de tildar **"Add to PATH"**.
- **`pip` no anda:** probá `pip3`. En Mac, probá `python3 -m pip install -r requirements.txt`.
- **La app no abre en localhost:5000:** fijate que la Terminal siga corriendo `python app.py`
  (no la cierres). Si dice "Address already in use", cerrá la otra ventana o reiniciá la compu.
- **`git push` te rechaza:** primero traé lo último con `git pull`, después `git push` de nuevo.
- **Cualquier error raro:** copiá el texto del error y pegáselo a Codex ("me da este error: ..."),
  o mandáselo a tu novio.

> 💡 Si toda esta instalación te resulta un lío, existe una versión de Codex **en el navegador**
> (web) que no requiere instalar NADA: se conecta a GitHub y editás escribiendo en español.
> Preguntale a tu novio si preferís esa.
