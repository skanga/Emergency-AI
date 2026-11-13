# IA de la Supervivencia (IA da Sobrevivência)

**Un asistente de supervivencia que funciona 100 % sin internet** — en Windows, Linux y macOS.

[🇧🇷 Português](README.pt.md) · [🇺🇸 English](README.en.md) · 🇪🇸 Español

Si internet, la electricidad y los servicios se caen, este kit sigue funcionando en una laptop o un pendrive:

- 📚 **Guías prácticas con fuentes citadas** (ES, PT, EN): agua, fuego, refugio, comida, huerta y cría de animales, recolección/pesca/caza, **primeros auxilios y medicina**, higiene y jabón casero, **alcohol** (fermentación, destilación, antiséptico y combustible), energía solar, radio y navegación, herramientas y nudos, salud mental y comunidad, y listas para 72 horas y **1 año**.
- 🤖 **IA local** que responde cualquier pregunta en lenguaje natural **citando las fuentes** — corre en tu propia computadora (llama.cpp u Ollama); nada sale a internet.
- 🌐 **Bibliotecas offline de Kiwix**: Wikipedia de medicina, manuales post-desastre, *Donde no hay doctor*, iFixit, Appropedia y más — la IA también busca en ellas.
- 📱 **Interfaz web** en el navegador, que se puede compartir en la red local (otros teléfonos se conectan por Wi-Fi, aun sin internet).
- 🔍 **Modo sin IA**: incluso sin modelo, la búsqueda en las guías funciona en cualquier PC con Python.

> ⚠️ **Aviso:** contenido educativo. No reemplaza a médicos, bomberos ni servicios de emergencia. Las orientaciones de salud siguen directrices públicas (OMS, Cruz Roja/IFRC, AHA, CDC, Hesperian…) citadas en cada sección.

---

## Cómo funciona

```
 Pregunta ──► búsqueda en las guías del kit (BM25) ─┐
          └─► búsqueda en Kiwix (archivos .zim) ─────┼─► modelo de lenguaje local ──► respuesta con fuentes [1] [2]
                                                     └─► (¿sin modelo? muestra los fragmentos más relevantes)
```

Los archivos grandes (modelos, bases ZIM, motores) **no van al git**: el repositorio queda liviano y cada persona arma su kit con el preparador.

---

## Inicio rápido

### 1. Descarga el repositorio

```bash
git clone https://github.com/skanga/Survival-AI.git
cd Survival-AI
```

### 2. Prepara el kit (con internet, una sola vez)

| Sistema | Cómo ejecutar |
|---|---|
| **Windows** | doble clic en `prepare-kit.bat` |
| **macOS** | doble clic en `prepare-kit.command` (la 1.ª vez: clic derecho › Abrir) |
| **Linux** | `./prepare-kit.sh --lang es` |

El preparador pregunta:

1. **Modelo de IA:** `light` (1 GB, 4 GB de RAM), `standard` (2 GB, 8 GB de RAM — recomendado), `strong` (4,7 GB, 16 GB de RAM).
2. **Bibliotecas Kiwix:** `minimal` (~3 GiB), `recommended` (~8 GiB) o `full` (~77 GiB, Wikipedia sin imágenes).
3. **Bibliotecas archivadas opcionales:** copias antiguas de WikEM y wikiHow, con fecha y tamaño. Ninguna se selecciona de forma predeterminada, tampoco en `full`.
4. **Sistemas:** solo esta computadora, o **Windows + Linux + macOS** (kit universal para pendrive).
5. **Python portátil:** para que el kit abra en computadoras sin Python.

**Kiwix** permite leer sitios guardados sin internet; un archivo **ZIM** contiene esas páginas. **WikEM** es una referencia de medicina de urgencias para profesionales; la copia opcional es de **junio de 2020** y puede estar desactualizada. **WikiMed** reúne artículos médicos de Wikipedia y es una colección distinta. **wikiHow** contiene guías ilustradas para tareas prácticas. Las copias archivadas son opcionales mediante `--archives`; consulta [fechas, tamaños y comandos](README.md#optional-archived-libraries).

Sin preguntas:

```bash
python survival.py --lang es prepare --model standard --zims recommended --os all --python
```

### 3. Úsalo (sin internet)

| Sistema | Cómo abrir |
|---|---|
| **Windows** | `start.bat --lang es` (o doble clic en `start.bat` y botón **ES**) |
| **macOS** | `start.command` |
| **Linux** | `./start.sh --lang es` |

El navegador abre <http://127.0.0.1:8090>. Para dejar el español como predeterminado, crea `config/settings.local.json` con `{ "language": "es" }`.

### 4. Llévalo en un pendrive

Copia **toda la carpeta** a un pendrive o disco externo formateado en **exFAT** (funciona en los tres sistemas y admite archivos de más de 4 GB).

---

## Otras formas de uso

```bash
python survival.py --lang es chat                    # chat en la terminal
python survival.py --lang es ask "¿cómo preparo suero oral casero?"
python survival.py --lang es search quemadura
python survival.py status
python survival.py start --host 0.0.0.0              # compartir en la red local
python survival.py prepare --search survival         # buscar más bibliotecas Kiwix
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

Código: [MIT](LICENSE). Guías en `knowledge/`: [CC BY-SA 4.0](LICENSE-CONTENT.md). Los modelos, Kiwix, llama.cpp y archivos ZIM descargados por el preparador tienen sus propias licencias. El modelo predeterminado (Qwen2.5 3B) usa la *Qwen Research License*; para uso comercial elige `light` o `strong` (Apache 2.0).
