# Emergency AI

**Conocimiento y asistencia sin internet cuando los servicios dejan de funcionar.** — en Windows, Linux y macOS.

[🇧🇷 Português](README.pt.md) · [🇺🇸 English](README.md) · 🇪🇸 Español

Si internet, la electricidad y los servicios se caen, este kit sigue funcionando en una laptop o un pendrive:

- 📚 **Guías prácticas con fuentes citadas** (ES, PT, EN): agua, fuego, refugio, comida, huerta y cría de animales, recolección/pesca/caza, **primeros auxilios y medicina**, higiene y jabón casero, **alcohol** (fermentación, destilación, antiséptico y combustible), energía solar, radio y navegación, herramientas y nudos, salud mental y comunidad, y listas para 72 horas y **1 año**.
- 🤖 **IA local** que responde cualquier pregunta en lenguaje natural **citando las fuentes** — corre en tu propia computadora (llama.cpp u Ollama); nada sale a internet.
- 🌐 **Bibliotecas offline de Kiwix**: Wikipedia de medicina, manuales post-desastre, *Donde no hay doctor*, iFixit, Appropedia y más — la IA también busca en ellas.
- 📱 **Interfaz web** en el navegador, que se puede compartir en la red local (otros teléfonos se conectan por Wi-Fi, aun sin internet).
- 🔍 **Modo sin IA**: incluso sin modelo, la búsqueda en las guías funciona en cualquier PC con Python.

> ⚠️ **Aviso:** contenido educativo. No reemplaza a médicos, bomberos ni servicios de emergencia. Las orientaciones de salud siguen directrices públicas (OMS, Cruz Roja/IFRC, AHA, CDC, Hesperian…) citadas en cada sección.

---

## Cómo funciona

CUDA es opcional: la configuración ofrece la descarga al detectar una GPU NVIDIA. Para añadirlo a un kit con opciones guardadas, usa `.\run.bat prepare --resume --cuda --yes` o `./run.sh prepare --resume --cuda --yes`. La descarga incluye las bibliotecas necesarias, sin exigir el toolkit de desarrollo CUDA. En Windows/Linux, el modo `auto` intenta CUDA, Vulkan y CPU, en ese orden. `--no-cuda` evita nuevas descargas, pero no elimina el motor instalado. [Compatibilidad y detalles](README.md#quick-start).

La preparación incluye motores CPU y Vulkan separados en Windows/Linux y usa Metal en macOS. En cada inicio, el kit detecta las GPU disponibles e intenta usar la CPU si falla el inicio con GPU. Los controladores deben estar instalados. Para un kit con opciones guardadas, ejecuta `.\run.bat prepare --resume --yes` (Windows) o `./run.sh prepare --resume --yes` (Linux/macOS) para añadir el nuevo motor. La opción `llm_acceleration` en `config/settings.local.json` acepta `auto` (predeterminado), `cpu`, `cuda`, `vulkan` o `metal`. Consulta los [detalles de configuración](README.md#configuration).

```
 Pregunta ──► búsqueda en las guías del kit (BM25) ─┐
          └─► búsqueda en Kiwix (archivos .zim) ─────┼─► modelo de lenguaje local ──► respuesta con fuentes [1] [2]
                                                     └─► (¿sin modelo? muestra los fragmentos más relevantes)
```

Los archivos grandes (modelos, bases ZIM, motores) **no van al git**: el repositorio queda liviano y cada persona arma su kit con el comando `prepare`.

---

## Inicio rápido

### 1. Descarga el repositorio

**Sin Git ni Python instalado:** abre una terminal en la carpeta donde quieras guardar el kit. El instalador crea una subcarpeta `Emergency-AI`, o usa la carpeta actual si ya tiene ese nombre y está vacía, salvo por `install.bat` / `install.sh`. El kit incluye el código, los lanzadores y Python portátil para esta computadora.

Windows (PowerShell):

```powershell
curl.exe -fL https://raw.githubusercontent.com/skanga/Emergency-AI/main/install.bat -o install.bat
if ($LASTEXITCODE -eq 0) { .\install.bat }
```

Linux / macOS:

```sh
curl -fL https://raw.githubusercontent.com/skanga/Emergency-AI/main/install.sh -o install.sh && sh install.sh
```

Necesita internet, sin permisos de administrador. Acepta carpetas nuevas o vacías, salvo por los instaladores; no actualiza un kit instalado. Python tiene una versión fija y SHA-256 verificado. Los modelos y las bibliotecas son opcionales al abrir el kit. Consulta [requisitos y detalles](README.md#1-download-the-kit-no-git-or-python-required). El script se guarda antes de ejecutarlo para permitir su revisión. En Windows, todo está en un único archivo `.bat`, con código PowerShell integrado.

Al terminar, el instalador ofrece ejecutar `run.bat prepare` o `run.sh prepare` para configurar los componentes opcionales. Pulsa Enter o responde `y` para empezar; responde `n` para dejarlo para después. Sin terminal interactiva, se omite esta pregunta. Se reutiliza Python de esta computadora; los otros sistemas seleccionados reciben sus propios runtimes cuando sea necesario.

Alternativa para quienes ya usan Git y Python:

```bash
git clone https://github.com/skanga/Emergency-AI.git
cd Emergency-AI
```

### 2. Abre el kit

| Sistema | Cómo ejecutar |
|---|---|
| **Windows** | doble clic en `.\run.bat` |
| **macOS** | doble clic en `run.command` (la 1.ª vez: clic derecho › Abrir) |
| **Linux** | `./run.sh --lang es` |

En el primer uso, elige descargar los componentes opcionales (con internet) o abrir las guías incluidas. Se recuerda la elección de usar solo las guías. Si falta algún componente seleccionado, puedes reanudar la preparación o continuar con lo disponible. Sin una terminal interactiva, la aplicación inicia sin preguntas ni descargas.

Usa `.\run.bat prepare` en Windows o `./run.sh prepare` en Linux/macOS para elegir componentes. Añade `--resume` para reanudar las opciones guardadas en esta computadora; usa `status` para revisar el kit. Se necesita Python 3.8+ instalado o una copia portátil compatible dentro del kit.

El comando `prepare` pregunta:

1. **Modelo de IA:** `lfm3-1.7b` (default, ~1.1 GB, 8 GB RAM), `gemma4-e2b` (~3.2 GB, 16 GB RAM), `qwen35-9b` (~6.2 GB, 24 GB RAM). [Model choices / licencias](README.md#model-choices).
2. **Bibliotecas Kiwix:** `minimal` (~3 GiB), `recommended` (~8 GiB) o `full` (~77 GiB, Wikipedia sin imágenes).
3. **Bibliotecas archivadas opcionales:** copias antiguas de WikEM y wikiHow, con fecha y tamaño. Ninguna se selecciona de forma predeterminada, tampoco en `full`.
4. **Sistemas:** solo esta computadora, o **Windows + Linux + macOS** (kit universal para pendrive).
5. **Python portátil:** la preparación indica qué runtimes instalados se reutilizarán. Si todos los sistemas seleccionados ya tienen Python, omite esta pregunta. De lo contrario, pregunta solo por descargar o reparar los sistemas restantes; rechazar conserva las copias existentes.

**Kiwix** permite leer sitios guardados sin internet; un archivo **ZIM** contiene esas páginas. **WikEM** es una referencia de medicina de urgencias para profesionales; la copia opcional es de **junio de 2020** y puede estar desactualizada. **WikiMed** reúne artículos médicos de Wikipedia y es una colección distinta. **wikiHow** contiene guías ilustradas para tareas prácticas. Las copias archivadas son opcionales mediante `--archives`; consulta [fechas, tamaños y comandos](README.md#optional-archived-libraries).

Sin preguntas:

**Windows (PowerShell):**

```powershell
.\run.bat --lang es prepare --model gemma4-e2b --zims recommended --os all --python
```

**Linux / macOS:**

```sh
./run.sh --lang es prepare --model gemma4-e2b --zims recommended --os all --python
```

### 3. Úsalo (sin internet)

| Sistema | Cómo abrir |
|---|---|
| **Windows** | `.\run.bat --lang es` (o doble clic en `.\run.bat` y botón **ES**) |
| **macOS** | `run.command` |
| **Linux** | `./run.sh --lang es` |

El navegador abre <http://127.0.0.1:8090>. El acceso desde la red local está activado de forma predeterminada. La consola muestra la dirección de red y un código QR para teléfonos en la misma red, incluso sin internet. Usa `--local-only` para permitir el acceso solo desde esta computadora. Para dejar el español como predeterminado, crea `config/settings.local.json` con `{ "language": "es" }`.

### 4. Llévalo en un pendrive

Copia **toda la carpeta** a un pendrive o disco externo formateado en **exFAT** (funciona en los tres sistemas y admite archivos de más de 4 GB).

---

## Otras formas de uso

**Windows (PowerShell):**

```powershell
.\run.bat --lang es chat                    # chat en la terminal
.\run.bat --lang es ask "¿cómo preparo suero oral casero?"
.\run.bat --lang es search quemadura
.\run.bat status
.\run.bat start --local-only                # desactivar el acceso desde la red local
.\run.bat prepare --search survival         # buscar más bibliotecas Kiwix
```

**Linux / macOS:**

```sh
./run.sh --lang es chat                    # chat en la terminal
./run.sh --lang es ask "¿cómo preparo suero oral casero?"
./run.sh --lang es search quemadura
./run.sh status
./run.sh start --local-only                # desactivar el acceso desde la red local
./run.sh prepare --search survival         # buscar más bibliotecas Kiwix
```

**Ollama:** si usas [Ollama](https://ollama.com), ejecuta `ollama pull qwen2.5:3b` — se detecta automáticamente. También funciona cualquier servidor local compatible con la API de OpenAI (LM Studio, llamafile, KoboldCpp, Jan): ajusta `llm_url`.

**Kiwix Desktop:** [Kiwix Desktop](https://kiwix.org) abre los archivos `.zim` de `zim/`. Para que la IA use su *Servidor local*, pon `{ "kiwix_url": "http://127.0.0.1:<puerto>" }` en `config/settings.local.json`. El paquete de Kiwix Desktop para Windows (~150 MB) supera el límite de 100 MB por archivo de GitHub: publícalo como **adjunto de una Release** en lugar de hacer commit.

## Agrega tu propio conocimiento

Coloca archivos `.md` o `.txt` en `knowledge/extra/` (recetas familiares, mapas del barrio, contactos, manuales). Se indexan y la IA los cita.

## Requisitos

- **Mínimo (solo búsqueda):** cualquier PC con Python 3.8+.
- **Con IA:** 4 GB de RAM (modelo ligero), 8 GB recomendados; CPU x86-64 con AVX2 o Apple Silicon/ARM64. No requiere tarjeta gráfica.
- **Disco:** de 3 GB (kit mínimo) a 100+ GB (kit completo).

## Pruebas

```bash
python -m unittest discover -s tests
```

## Licencias

Código: [MIT](LICENSE). Guías en `knowledge/`: [CC BY-SA 4.0](LICENSE-CONTENT.md). Los modelos, Kiwix, llama.cpp y archivos ZIM descargados con el comando `prepare` tienen sus propias licencias.  Gemma 4 E2B / Qwen / Ministral: Apache 2.0. LFM3: LFM Open License v1.0. [Details](README.md#model-choices).
