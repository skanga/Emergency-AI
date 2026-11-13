# Emergency AI

**Conhecimento e assistência offline quando os serviços ficam indisponíveis.** — no Windows, Linux e macOS.

[🇺🇸 English](README.md) · 🇧🇷 Português · [🇪🇸 Español](README.es.md)

Se a internet, a energia e os serviços pararem, este kit continua funcionando num notebook ou pendrive:

- 📚 **Guias práticos com fontes citadas** (PT, EN e ES): água, fogo, abrigo, comida, horta e criação, coleta/pesca/caça, **primeiros socorros e medicina**, higiene e sabão caseiro, **álcool** (fermentação, destilação, antisséptico e combustível), energia solar, rádio e navegação, ferramentas e nós, saúde mental e comunidade, e checklists para 72 horas e **1 ano**.
- 🤖 **IA local** que responde qualquer pergunta em linguagem natural, **citando as fontes** — roda no próprio computador (llama.cpp ou Ollama), nada vai para a internet.
- 🌐 **Bibliotecas offline do Kiwix**: Wikipedia de medicina, manuais pós-desastre, *Where There Is No Doctor*, iFixit, Appropedia e outras — a IA busca nelas também.
- 📱 **Interface web** que abre no navegador e pode ser compartilhada na rede local (outros celulares acessam pelo Wi-Fi, mesmo sem internet).
- 🔍 **Modo sem IA**: mesmo sem modelo baixado, a busca nos guias funciona em qualquer PC com Python.

> ⚠️ **Aviso:** conteúdo educativo. Não substitui médicos, bombeiros ou defesa civil. As orientações de saúde seguem diretrizes públicas (OMS, Cruz Vermelha/IFRC, AHA, Ministério da Saúde, CDC, Hesperian…) citadas em cada seção.

---

## Como funciona

```
 Pergunta ──► busca nos guias do kit (BM25) ─┐
          └─► busca no Kiwix (arquivos .zim) ─┼─► modelo de linguagem local ──► resposta com [1] [2] fontes
                                              └─► (sem modelo? mostra os trechos mais relevantes)
```

| Peça | O que é | Onde fica |
|---|---|---|
| `survival.py` + `app/` | A IA (só biblioteca padrão do Python, sem `pip install`) | repositório |
| `knowledge/pt|en|es/` | Guias de sobrevivência em Markdown | repositório |
| `knowledge/extra/` | **Seus** documentos `.md`/`.txt` (entram na busca e na IA) | repositório |
| `runtime/llama.cpp/` | Motor que roda o modelo de IA | baixado pelo preparador |
| `models/*.gguf` | Modelo de linguagem (1–5 GB) | baixado pelo preparador |
| `runtime/kiwix-tools/` + `zim/*.zim` | Servidor e bibliotecas do Kiwix | baixado pelo preparador |
| `runtime/python/` | Python portátil (para PCs sem Python) | baixado pelo preparador |

Os arquivos grandes **não vão para o git** (veja `.gitignore`): o repositório fica light, e cada pessoa monta o seu kit com o preparador.

---

## Começo rápido

### 1. Baixe o repositório

```bash
git clone https://github.com/skanga/Emergency-AI.git
cd Emergency-AI
```

### 2. Abra o kit

| Sistema | Como rodar |
|---|---|
| **Windows** | clique duas vezes em `.\run.bat` |
| **macOS** | clique duas vezes em `run.command` (1ª vez: botão direito › Abrir) |
| **Linux** | `./run.sh` |

No primeiro uso, escolha baixar os componentes opcionais (com internet) ou abrir os guias incluídos. A escolha de usar apenas os guias é lembrada. Se faltar algum componente selecionado, você pode retomar a preparação ou continuar com o que está disponível. Sem terminal interativo, o aplicativo inicia sem perguntas nem downloads.

Use `.\run.bat prepare` no Windows ou `./run.sh prepare` no Linux/macOS para escolher componentes. Acrescente `--resume` para retomar as escolhas salvas neste computador; use `status` para verificar o kit. É necessário Python 3.8+ instalado ou uma cópia portátil compatível no kit.

O preparador pergunta:

1. **Modelo de IA:** `lfm3-1.7b` (~1.1 GB, 8 GB RAM), `gemma4-e2b` (default, ~3.2 GB, 16 GB RAM), `qwen35-9b` (~6.2 GB, 24 GB RAM). [Model choices / licenças](README.md#model-choices).
2. **Bibliotecas Kiwix:** `minimal` (~3 GiB), `recommended` (~8 GiB) ou `full` (~77 GiB, Wikipedia sem imagens).
3. **Bibliotecas arquivadas opcionais:** cópias antigas do WikEM e wikiHow, com data e tamanho. Nenhuma é selecionada por padrão, nem no perfil `full`.
4. **Sistemas:** só este computador, ou **Windows + Linux + macOS** (kit universal para pendrive).
5. **Python portátil:** para o kit abrir em computadores sem Python.

**Kiwix** permite ler sites salvos sem internet; um arquivo **ZIM** contém essas páginas. **WikEM** é uma referência de medicina de emergência para profissionais; a cópia opcional é de **junho de 2020** e pode estar desatualizada. **WikiMed** reúne artigos médicos da Wikipédia e é uma coleção diferente. **wikiHow** contém guias ilustrados para tarefas práticas. As cópias arquivadas são opcionais via `--archives`; consulte [datas, tamanhos e comandos](README.md#optional-archived-libraries).

Sem perguntas (ex.: para automatizar):

```bash
python survival.py prepare --model gemma4-e2b --zims recommended --os all --python
```

> Se faltar Python para rodar o preparador: instale em <https://www.python.org/downloads/> (no Windows marque *Add python.exe to PATH*). Depois o kit leva um Python portátil junto.

### 3. Use (sem internet)

| Sistema | Como abrir |
|---|---|
| **Windows** | `.\run.bat` |
| **macOS** | `run.command` |
| **Linux** | `./run.sh` |

O navegador abre em <http://127.0.0.1:8090>. Para inglês ou espanhol: `.\run.bat --lang en` / `./run.sh --lang es` (ou use os botões PT/EN/ES na interface).

### 4. Leve no pendrive

Copie **a pasta inteira** para um pendrive ou HD externo (formatado em **exFAT**, que funciona nos três sistemas e aceita arquivos com mais de 4 GB). Pronto: é só abrir o `run` correspondente em qualquer computador.

---

## Outras formas de usar

```bash
python survival.py chat                       # conversa no terminal
python survival.py ask "como fazer soro caseiro?"
python survival.py search queimadura          # busca rápida nos guias
python survival.py status                     # o que está instalado e ativo
python survival.py start --host 0.0.0.0       # compartilhar na rede local (Wi-Fi)
python survival.py prepare --search survival  # descobrir mais bases no catálogo Kiwix
```

**Compartilhar com a comunidade:** com `--host 0.0.0.0`, qualquer celular conectado ao mesmo roteador (mesmo sem internet) abre o endereço mostrado no terminal, ex.: `http://192.168.0.10:8090`.

### Usando Ollama em vez do llama.cpp

Se você já usa [Ollama](https://ollama.com): `ollama pull qwen2.5:3b` e pronto — a IA detecta o Ollama sozinha. Para outro modelo, crie `config/settings.local.json`:

```json
{ "ollama_model": "llama3.2:3b" }
```

Também funciona com qualquer servidor compatível com a API da OpenAI rodando localmente (LM Studio, llamafile, KoboldCpp, Jan): ajuste `llm_url`.

### Usando o Kiwix Desktop

O [Kiwix Desktop](https://kiwix.org) abre os arquivos `.zim` da pasta `zim/` com uma interface de leitura completa. Se preferir que a IA use o servidor do Kiwix Desktop (menu *Servidor local / Local Kiwix Server*), coloque a porta dele em `config/settings.local.json`:

```json
{ "kiwix_url": "http://127.0.0.1:8080" }
```

> 💡 O instalador do Kiwix Desktop para Windows (~150 MB) é maior que o limite de 100 MB por arquivo do GitHub. Para distribuí-lo junto, publique-o como **anexo de uma Release** do repositório (limite de 2 GB por arquivo) em vez de fazer commit.

---

## Adicionando seu próprio conhecimento

Coloque arquivos `.md` ou `.txt` em `knowledge/extra/` (receitas da família, mapa do bairro, contatos, manuais de equipamentos, bulas). Eles entram no índice e a IA passa a citá-los. Para traduzir ou ampliar os guias oficiais, edite `knowledge/<idioma>/` mantendo os mesmos nomes de arquivo nos três idiomas.

## Configuração

`config/settings.json` tem os padrões. Para mudar algo sem mexer no arquivo versionado, crie `config/settings.local.json` só com o que quer alterar (ele é ignorado pelo git). Principais opções:

| Chave | Padrão | Para quê |
|---|---|---|
| `language` | `en` | idioma padrão (`pt`, `en`, `es`) |
| `web_port` | `8090` | porta da interface |
| `llm_backend` | `auto` | `auto`, `openai` (llama.cpp etc.), `ollama` ou `none` |
| `model_file` | — | nome do `.gguf` a usar quando houver vários |
| `llm_context` | `8192` | tamanho do contexto do modelo |
| `llm_threads` | `0` | núcleos de CPU (0 = automático) |
| `kiwix_url` | `http://127.0.0.1:8092` | servidor Kiwix |
| `search_results` | `5` | trechos dos guias enviados à IA |

## Requisitos

- **Mínimo (só busca):** qualquer PC com Python 3.8+.
- **Com IA:** 4 GB de RAM (modelo leve), 8 GB recomendados; CPU x86-64 com AVX2 ou Apple Silicon/ARM64. Não precisa de placa de vídeo.
- **Disco:** 3 GB (kit mínimo) até 100+ GB (kit completo).

## Testes

```bash
python -m unittest discover -s tests
```

## Estrutura

```
Emergency-AI/
├── run.bat / run.sh / run.command          ← abrir o kit
├── survival.py                                    ← ponto de entrada (CLI)
├── app/          knowledge.py (busca) · engine.py (RAG) · llm.py · kiwix.py · server.py · launcher.py · prepare.py
├── web/          interface (HTML/CSS/JS sem dependências)
├── knowledge/    pt/ en/ es/ (guias) · extra/ (seus documentos)
├── config/       settings.json · models.json · zims.json
├── models/  zim/  runtime/                             ← preenchidos pelo preparador (fora do git)
└── tests/
```

## Licenças

- Código: [MIT](LICENSE).
- Guias em `knowledge/`: [CC BY-SA 4.0](LICENSE-CONTENT.md).
- Modelos, Kiwix, llama.cpp e bases ZIM baixados pelo preparador têm suas próprias licenças (veja `config/models.json` e as páginas de cada projeto).  Gemma 4 E2B / Qwen / Ministral: Apache 2.0. LFM3: LFM Open License v1.0. [Details](README.md#model-choices).

## Contribua

Correções com fonte, novos guias e traduções são bem-vindos. Mantenha uma linha `> Fonte:` em cada seção com orientação técnica ou de saúde.
