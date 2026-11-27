/* Emergency AI — UI (no external libraries, works offline) */
(function () {
  "use strict";

  const I18N = {
    pt: {
      title: "Emergency AI", subtitle: "Conhecimento e assistência offline quando os serviços ficam indisponíveis.", ask: "Perguntar à IA", filter: "Buscar nos guias…",
      index: "Índice", foot: "Imprima os guias críticos: papel não precisa de energia.", emerg: "Emergência?",
      emergTxt: "Se houver telefone: SAMU 192 · Bombeiros 193 · Europa 112 · EUA 911",
      hello: "Como posso ajudar?",
      modelLabel: "Modelo de IA", modelProgress: "Carregando modelo", modelLoadingShort: "Carregando…", modelQueuedShort: "Troca na fila…",
      modelNote: "Aplica-se a todos os navegadores conectados a este servidor. Apenas um modelo fica carregado por vez.",
      libraryLabel: "Bibliotecas Kiwix", libraryAll: "Todas as bibliotecas", librariesAll: "Bibliotecas: todas",
      librariesSelected: "Bibliotecas: {n} selecionadas", libraryEmpty: "Nenhuma biblioteca disponível. Inicie o Kiwix com as bibliotecas instaladas.",
      libraryNone: "Nenhuma biblioteca selecionada. A busca usa apenas os guias incluídos.",
      libraryDisabled: "Ative a opção de usar Kiwix abaixo da pergunta para pesquisar nestas bibliotecas.",
      libraryNote: "Filtra as fontes das bibliotecas apenas neste navegador. Os guias incluídos são sempre pesquisados.",
      modelChoose: "Escolha um modelo instalado", modelEmpty: "Nenhum modelo GGUF instalado. Execute 'python emergency.py prepare' para adicionar um.",
      modelDisabled: "Troca indisponível para IA externa ou desativada.", modelEngine: "Execute 'python emergency.py prepare' para instalar o llama.cpp e trocar modelos aqui.",
      modelQueued: "Aguardando a resposta atual terminar…", modelStopping: "Descarregando o modelo atual…",
      modelLoading: "Carregando {model}… {seconds}s", modelReady: "Selecionado: {model}",
      modelFailed: "Falha na troca. Tente novamente ou escolha outro modelo. ", modelOffline: "Não foi possível consultar os modelos. Reconectando…",
      helloTxt: "Conhecimento e assistência offline quando os serviços ficam indisponíveis. As respostas citam os guias do kit e as bibliotecas offline.",
      placeholder: "Ex.: como purificar água da chuva?", useKiwix: "usar bibliotecas Kiwix", back: "Voltar para a IA",
      print: "Imprimir", sources: "Referências recuperadas", kit: "guia", kiwix: "Kiwix", thinking: "Procurando nas fontes…",
      llmOn: "IA: ", llmOff: "IA: só busca", kiwixOn: "Kiwix: {n} bases", kiwixOff: "Kiwix: desligado",
      modeLlm: "resposta da IA · trechos locais fornecidos", modeUngrounded: "resposta da IA — sem fontes locais", modeDisabled: "modo busca (IA desativada)", modeFailed: "modo busca (resposta da IA indisponível)", modeSearch: "modo busca (sem modelo de IA disponível)", error: "Erro: ",
      noResults: "Nada encontrado.", llmTip: "Sem modelo de IA ativo: execute 'python emergency.py prepare' para baixar um.",
      quick: [
        ["Água", "Como purificar água para beber?"],
        ["Sangramento", "Como parar um sangramento grave?"],
        ["RCP", "Como fazer massagem cardíaca (RCP)?"],
        ["Diarreia", "Como fazer soro caseiro?"],
        ["Fogo", "Como fazer fogo sem fósforo nem isqueiro?"],
        ["Queimadura", "O que fazer em caso de queimadura?"],
        ["Comida", "Como conservar carne sem geladeira?"],
        ["Álcool", "Como fazer álcool 70% para desinfetar?"],
      ],
    },
    en: {
      title: "Emergency AI", subtitle: "Offline knowledge and assistance when services go down.", ask: "Ask the AI", filter: "Search the guides…",
      index: "Contents", foot: "Print the critical guides: paper needs no power.", emerg: "Emergency?",
      emergTxt: "If phones work: US/Canada 911 · Europe 112 · UK 999 · Brazil 192/193",
      hello: "How can I help?",
      modelLabel: "AI model", modelProgress: "Loading model", modelLoadingShort: "Loading…", modelQueuedShort: "Switch queued…",
      modelNote: "Applies to all browsers connected to this server. One model stays loaded at a time.",
      libraryLabel: "Kiwix libraries", libraryAll: "All libraries", librariesAll: "Libraries: All",
      librariesSelected: "Libraries: {n} selected", libraryEmpty: "No libraries available. Start Kiwix with your installed libraries.",
      libraryNone: "No libraries selected. Searches use only the included guides.",
      libraryDisabled: "Enable the Kiwix option below your question to search these libraries.",
      libraryNote: "Filters library sources for this browser only. Included guides are always searched.",
      modelChoose: "Choose an installed model", modelEmpty: "No GGUF models installed. Run 'python emergency.py prepare' to add one.",
      modelDisabled: "Switching is unavailable for externally managed or disabled AI engines.", modelEngine: "Run 'python emergency.py prepare' to install llama.cpp and switch models here.",
      modelQueued: "Waiting for the current answer to finish…", modelStopping: "Unloading the current model…",
      modelLoading: "Loading {model}… {seconds}s", modelReady: "Selected: {model}",
      modelFailed: "Switch failed. Retry or choose another model. ", modelOffline: "Cannot check models. Reconnecting…",
      helloTxt: "Offline knowledge and assistance when services go down. Answers cite the kit guides and offline libraries.",
      placeholder: "E.g. how do I purify rainwater?", useKiwix: "use Kiwix libraries", back: "Back to the AI",
      print: "Print", sources: "Retrieved references", kit: "guide", kiwix: "Kiwix", thinking: "Searching the sources…",
      llmOn: "AI: ", llmOff: "AI: search only", kiwixOn: "Kiwix: {n} libraries", kiwixOff: "Kiwix: off",
      modeLlm: "AI answer · local passages supplied", modeUngrounded: "AI answer — not backed by local sources", modeDisabled: "search mode (AI disabled)", modeFailed: "search mode (AI answer unavailable)", modeSearch: "search mode (no AI model available)", error: "Error: ",
      noResults: "Nothing found.", llmTip: "No AI model running: run 'python emergency.py prepare' to download one.",
      quick: [
        ["Water", "How do I purify water for drinking?"],
        ["Bleeding", "How do I stop severe bleeding?"],
        ["CPR", "How do I do CPR?"],
        ["Diarrhea", "How do I make oral rehydration solution?"],
        ["Fire", "How do I make fire without matches or a lighter?"],
        ["Burns", "What should I do for a burn?"],
        ["Food", "How can I preserve meat without a fridge?"],
        ["Alcohol", "How do I make 70% alcohol for disinfection?"],
      ],
    },
    es: {
      title: "Emergency AI", subtitle: "Conocimiento y asistencia sin internet cuando los servicios dejan de funcionar.", ask: "Preguntar a la IA", filter: "Buscar en las guías…",
      index: "Índice", foot: "Imprime las guías críticas: el papel no necesita energía.", emerg: "¿Emergencia?",
      emergTxt: "Si hay teléfono: 112 Europa · 911 gran parte de América · Brasil 192/193",
      hello: "¿Cómo puedo ayudar?",
      modelLabel: "Modelo de IA", modelProgress: "Cargando modelo", modelLoadingShort: "Cargando…", modelQueuedShort: "Cambio en espera…",
      modelNote: "Se aplica a todos los navegadores conectados a este servidor. Solo se carga un modelo a la vez.",
      libraryLabel: "Bibliotecas Kiwix", libraryAll: "Todas las bibliotecas", librariesAll: "Bibliotecas: todas",
      librariesSelected: "Bibliotecas: {n} seleccionadas", libraryEmpty: "No hay bibliotecas disponibles. Inicia Kiwix con las bibliotecas instaladas.",
      libraryNone: "Ninguna biblioteca seleccionada. La búsqueda usa solo las guías incluidas.",
      libraryDisabled: "Activa la opción de usar Kiwix debajo de la pregunta para buscar en estas bibliotecas.",
      libraryNote: "Filtra las fuentes de las bibliotecas solo en este navegador. Las guías incluidas siempre se consultan.",
      modelChoose: "Elige un modelo instalado", modelEmpty: "No hay modelos GGUF instalados. Ejecuta 'python emergency.py prepare' para añadir uno.",
      modelDisabled: "El cambio no está disponible para motores de IA externos o desactivados.", modelEngine: "Ejecuta 'python emergency.py prepare' para instalar llama.cpp y cambiar modelos aquí.",
      modelQueued: "Esperando a que termine la respuesta actual…", modelStopping: "Descargando el modelo actual de la memoria…",
      modelLoading: "Cargando {model}… {seconds}s", modelReady: "Seleccionado: {model}",
      modelFailed: "El cambio falló. Reintenta o elige otro modelo. ", modelOffline: "No se pueden consultar los modelos. Reconectando…",
      helloTxt: "Conocimiento y asistencia sin internet cuando los servicios dejan de funcionar. Las respuestas citan las guías del kit y las bibliotecas offline.",
      placeholder: "P. ej.: ¿cómo purifico agua de lluvia?", useKiwix: "usar bibliotecas Kiwix", back: "Volver a la IA",
      print: "Imprimir", sources: "Referencias recuperadas", kit: "guía", kiwix: "Kiwix", thinking: "Buscando en las fuentes…",
      llmOn: "IA: ", llmOff: "IA: solo búsqueda", kiwixOn: "Kiwix: {n} bases", kiwixOff: "Kiwix: apagado",
      modeLlm: "respuesta de IA · fragmentos locales proporcionados", modeUngrounded: "respuesta de IA — sin fuentes locales", modeDisabled: "modo búsqueda (IA desactivada)", modeFailed: "modo búsqueda (respuesta de IA no disponible)", modeSearch: "modo búsqueda (sin modelo de IA disponible)", error: "Error: ",
      noResults: "No se encontró nada.", llmTip: "Sin modelo de IA activo: ejecuta 'python emergency.py prepare' para descargar uno.",
      quick: [
        ["Agua", "¿Cómo purificar agua para beber?"],
        ["Hemorragia", "¿Cómo detener una hemorragia grave?"],
        ["RCP", "¿Cómo hacer RCP (masaje cardíaco)?"],
        ["Diarrea", "¿Cómo preparar suero oral casero?"],
        ["Fuego", "¿Cómo hacer fuego sin fósforos ni encendedor?"],
        ["Quemaduras", "¿Qué hacer en caso de quemadura?"],
        ["Comida", "¿Cómo conservar carne sin refrigerador?"],
        ["Alcohol", "¿Cómo hacer alcohol al 70% para desinfectar?"],
      ],
    },
  };

  const $ = (s) => document.querySelector(s);
  const params = new URLSearchParams(location.search);
  let lang = params.get("lang") || store("lang") || "en";
  if (!I18N[lang]) lang = "en";
  let guides = [];
  let chatHistory = [];
  let busy = false;
  let status = null;
  let modelState = null;
  let modelRequest = false;
  let modelFetch = 0;
  let modelActionError = null;
  let modelMenuSignature = "";
  let modelUnavailable = false;
  let librarySelection = readLibrarySelection(); // null = all, [] = none
  let libraryMenuSignature = "";

  function readLibrarySelection() {
    try {
      const saved = JSON.parse(store("libraries"));
      return Array.isArray(saved) && saved.every((name) => typeof name === "string") ? saved : null;
    } catch (e) { return null; }
  }

  function libraryBooks() { return status && status.kiwix ? status.kiwix.books || [] : []; }

  function renderLibraries() {
    const books = libraryBooks();
    const selected = new Set(librarySelection === null ? books.map((b) => b.name) : librarySelection);
    const count = books.filter((b) => selected.has(b.name)).length;
    const enabled = $("#useKiwix").checked;
    const chip = $("#chipKiwix");
    chip.className = "chip" + (enabled && count ? " on" : "");
    chip.querySelector("span").textContent = !books.length || !enabled ? t("kiwixOff") :
      librarySelection === null ? t("librariesAll") : t("librariesSelected").replace("{n}", count);
    const signature = JSON.stringify([lang, books]);
    if (signature !== libraryMenuSignature) {
      libraryMenuSignature = signature;
      const options = $("#libraryOptions");
      options.replaceChildren();
      for (const book of books) {
        const label = document.createElement("label");
        label.className = "model-option library-option";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.dataset.library = book.name;
        const name = document.createElement("span");
        name.className = "library-name";
        name.textContent = book.title;
        const detail = document.createElement("small");
        detail.textContent = [book.lang, book.name].filter(Boolean).join(" · ");
        const documents = book.capabilities && book.capabilities.documents;
        if (documents && documents.state !== "not_applicable") detail.textContent += " · " + retrievalLabel(documents.state);
        name.append(detail);
        label.append(checkbox, name);
        options.append(label);
      }
    }
    $("#libraryOptions").querySelectorAll("input").forEach((box) => { box.checked = selected.has(box.dataset.library); });
    const all = $("#libraryAll");
    all.disabled = !books.length;
    all.checked = !!books.length && count === books.length;
    all.indeterminate = count > 0 && count < books.length;
    $("#libraryState").textContent = !books.length ? t("libraryEmpty") : !enabled ? t("libraryDisabled") : !count ? t("libraryNone") : "";
  }

  function saveLibraries(selection) {
    librarySelection = selection;
    store("libraries", JSON.stringify(selection));
    renderLibraries();
  }

  function store(k, v) {
    try {
      if (v === undefined) return localStorage.getItem("ias:" + k);
      localStorage.setItem("ias:" + k, v);
    } catch (e) { return null; }
  }
  const t = (k) => I18N[lang][k] ?? I18N.en[k] ?? k;

  // ---------------- markdown ----------------
  function normalizeArrows(s) {
    const arrows = {
      rightarrow: "→", longrightarrow: "→", to: "→",
      leftarrow: "←", longleftarrow: "←", gets: "←",
      leftrightarrow: "↔", longleftrightarrow: "↔",
      Rightarrow: "⇒", Longrightarrow: "⇒", implies: "⇒",
      Leftarrow: "⇐", Longleftarrow: "⇐",
      Leftrightarrow: "⇔", Longleftrightarrow: "⇔", iff: "⇔",
      uparrow: "↑", downarrow: "↓", updownarrow: "↕",
    };
    const names = Object.keys(arrows).join("|");
    const command = String.raw`\\(${names})(?![A-Za-z])`;
    // Strip math delimiters only around a single supported arrow expression.
    const wrapped = new RegExp(String.raw`\$\$\s*${command}\s*\$\$|\$\s*${command}\s*\$|\\\(\s*${command}\s*\\\)|\\\[\s*${command}\s*\\\]`, "g");
    s = s.replace(wrapped, (match) => arrows[match.match(/\\([A-Za-z]+)/)[1]]);
    return s.replace(new RegExp(command, "g"), (_, name) => arrows[name]);
  }
  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function slugify(s) {
    return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "section";
  }
  function inline(s, opts) {
    s = esc(s).replace(/[\u0000\u0001]/g, "");
    const codes = [], links = [];
    const protectLink = html => { links.push(html); return "\u0001" + (links.length - 1) + "\u0001"; };
    s = s.replace(/`([^`]+)`/g, (_, c) => { codes.push(c); return "\u0000" + (codes.length - 1) + "\u0000"; });
    s = normalizeArrows(s);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
    s = s.replace(/(^|[\s(])_([^_\n]+)_(?=[\s).,;:!?]|$)/g, "$1<em>$2</em>");
    s = s.replace(/\[((?:[^\[\]]|\[[^\[\]]*\])+)\]\(([^)\s]+)\)/g, (_, txt, href) => {
      const m = href.match(/^([\w-]+)\.md(#[\w-]+)?$/);
      if (m) return protectLink(`<a href="#" data-guide="${m[1]}" data-anchor="${(m[2] || "").slice(1)}">${txt}</a>`);
      if (/^https?:\/\//.test(href)) return protectLink(`<a href="${href}" target="_blank" rel="noopener">${txt}</a>`);
      return txt;
    });
    s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)\u0000\u0001]+[^\s<).,;\u0000\u0001])/g, (_, prefix, url) => prefix + protectLink(`<a href="${url}" target="_blank" rel="noopener">${url}</a>`));
    if (opts && opts.cites) s = s.replace(/\[(\d{1,2})\]/g, '<a href="#" class="cite" data-cite="$1">[$1]</a>');
    s = s.replace(/\u0001(\d+)\u0001/g, (_, i) => links[+i]);
    s = s.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[+i]}</code>`);
    return s;
  }
  function md(src, opts) {
    const lines = src.replace(/\r/g, "").split("\n");
    let out = "", i = 0;
    const isTableSep = (l) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(l);
    const cells = (l) => l.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
    while (i < lines.length) {
      let line = lines[i];
      if (/^\s*$/.test(line)) { i++; continue; }
      let m;
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
        const lvl = m[1].length, txt = m[2].trim();
        out += `<h${lvl} id="${slugify(txt)}">${inline(txt, opts)}</h${lvl}>`; i++; continue;
      }
      if (/^```/.test(line)) {
        let code = ""; i++;
        while (i < lines.length && !/^```/.test(lines[i])) code += lines[i++] + "\n";
        i++; out += `<pre><code>${esc(code)}</code></pre>`; continue;
      }
      if (/^\s*(---|\*\*\*)\s*$/.test(line)) { out += "<hr>"; i++; continue; }
      if (/^\s*>/.test(line)) {
        const buf = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) buf.push(lines[i++].replace(/^\s*>\s?/, ""));
        out += `<blockquote>${md(buf.join("\n"), opts)}</blockquote>`; continue;
      }
      if (/\|/.test(line) && i + 1 < lines.length && isTableSep(lines[i + 1])) {
        const head = cells(line); i += 2;
        let rows = "";
        while (i < lines.length && /\|/.test(lines[i]) && lines[i].trim()) {
          rows += "<tr>" + cells(lines[i]).map((c) => `<td>${inline(c, opts)}</td>`).join("") + "</tr>"; i++;
        }
        out += `<table><thead><tr>${head.map((c) => `<th>${inline(c, opts)}</th>`).join("")}</tr></thead><tbody>${rows}</tbody></table>`;
        continue;
      }
      if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
        out += list(lines, i, opts, (ni) => (i = ni)); continue;
      }
      const buf = [];
      while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|```|\s*>|\s*([-*+]|\d+[.)])\s+)/.test(lines[i]) &&
             !(/\|/.test(lines[i]) && i + 1 < lines.length && isTableSep(lines[i + 1]))) buf.push(lines[i++]);
      out += `<p>${inline(buf.join(" "), opts)}</p>`;
    }
    return out;
  }
  function list(lines, start, opts, setI) {
    const indent = (l) => l.match(/^\s*/)[0].length;
    const base = indent(lines[start]);
    const ordered = /^\s*\d+[.)]\s+/.test(lines[start]);
    let html = ordered ? "<ol>" : "<ul>", i = start;
    while (i < lines.length) {
      const l = lines[i];
      if (!l.trim()) { if (i + 1 < lines.length && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i + 1]) && indent(lines[i + 1]) >= base) { i++; continue; } break; }
      const ind = indent(l);
      const m = l.match(/^\s*([-*+]|\d+[.)])\s+(.*)$/);
      if (m && ind === base) {
        let txt = m[2], cls = "";
        const task = txt.match(/^\[( |x|X)\]\s+(.*)$/);
        if (task) { cls = ' class="task"'; txt = `<label><input type="checkbox"${task[1] !== " " ? " checked" : ""}>${inline(task[2], opts)}</label>`; }
        else txt = inline(txt, opts);
        i++;
        while (i < lines.length && lines[i].trim() && !/^\s*([-*+]|\d+[.)])\s+/.test(lines[i]) && indent(lines[i]) > base) txt += " " + inline(lines[i++].trim(), opts);
        if (i < lines.length && /^\s*([-*+]|\d+[.)])\s+/.test(lines[i]) && indent(lines[i]) > base) {
          txt += list(lines, i, opts, (ni) => (i = ni));
        }
        html += `<li${cls}>${txt}</li>`;
      } else if (m && ind > base) {
        html += list(lines, i, opts, (ni) => (i = ni));
      } else if (ind > base) {
        i++;
      } else break;
    }
    setI(i);
    return html + (ordered ? "</ol>" : "</ul>");
  }

  // ---------------- API ----------------
  async function api(path) {
    const r = await fetch(path);
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }

  const modelSwitching = () => modelRequest || (modelState && ["queued", "stopping", "loading"].includes(modelState.phase));

  function renderModelChip() {
    const chip = $("#chipLlm");
    let label;
    if (modelSwitching()) {
      label = t(modelState && modelState.phase === "queued" ? "modelQueuedShort" : "modelLoadingShort");
      if (modelState && modelState.elapsed) label += " " + Math.floor(modelState.elapsed) + "s";
      chip.className = "chip mid";
    } else if (modelState && modelState.phase === "error") {
      label = t("llmOff");
      chip.className = "chip mid";
    } else {
      const active = modelState && modelState.active || status && status.llm && status.llm.model;
      label = active ? t("llmOn") + active.replace(/\.gguf$/i, "") : t("llmOff");
      chip.className = status && status.llm ? "chip on" : "chip mid";
    }
    chip.querySelector("span").textContent = label;
    chip.setAttribute("aria-label", t("modelLabel") + ": " + label);
    chip.title = label + "\n" + t("modelChoose");
  }

  function renderModels() {
    const options = $("#modelOptions"), state = $("#modelState");
    const switching = modelSwitching();
    $("#send").disabled = busy || !!switching;
    $("#modelProgress").classList.toggle("hidden", !switching);
    renderModelChip();
    if (!modelState) return;
    const items = modelState.models || [];
    const disabled = !modelState.enabled || !!switching || modelUnavailable;
    const signature = JSON.stringify([lang, items, disabled, modelState.active]);
    // Leave focused menu options in place between background polls.
    if (signature !== modelMenuSignature) {
      modelMenuSignature = signature;
      options.replaceChildren();
      for (const model of items) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "model-option";
        button.dataset.modelFile = model.file;
        button.title = model.file;
        const selected = model.file === modelState.active;
        button.setAttribute("aria-pressed", String(selected));
        button.disabled = disabled || selected;
        const check = document.createElement("span");
        check.className = "model-check";
        check.textContent = selected ? "\u2713" : "";
        check.setAttribute("aria-hidden", "true");
        const name = document.createElement("span");
        name.className = "model-name";
        name.textContent = model.name;
        const size = document.createElement("small");
        size.textContent = (model.size_bytes / 1024 ** 3).toFixed(1) + " GiB";
        button.append(check, name, size);
        options.appendChild(button);
      }
    }
    state.className = modelActionError || modelState.phase === "error" ? "error" : "";
    if (modelUnavailable) state.textContent = t("modelOffline");
    else if (modelActionError) state.textContent = t("modelFailed") + modelActionError;
    else if (!modelState.enabled) state.textContent = t(modelState.reason === "missing_engine" ? "modelEngine" : "modelDisabled");
    else if (!items.length) state.textContent = t("modelEmpty");
    else if (modelState.phase === "queued") state.textContent = t("modelQueued");
    else if (modelState.phase === "stopping") state.textContent = t("modelStopping");
    else if (modelState.phase === "loading") state.textContent = t("modelLoading").replace("{model}", modelState.target).replace("{seconds}", Math.floor(modelState.elapsed));
    else if (modelState.phase === "error") state.textContent = t("modelFailed") + (modelState.error || "");
    else state.textContent = modelState.active ? t("modelReady").replace("{model}", modelState.active) : t("modelChoose");
  }

  async function loadModels() {
    const request = ++modelFetch;
    try {
      const next = await api("/api/models");
      if (request !== modelFetch) return;
      const oldPhase = modelState && modelState.phase;
      const activeChanged = modelState && modelState.active !== next.active;
      modelUnavailable = false;
      modelState = next;
      renderModels();
      if ((activeChanged || oldPhase !== next.phase) && ["ready", "error"].includes(next.phase)) loadStatus();
    } catch (e) {
      if (request !== modelFetch) return;
      modelUnavailable = true;
      renderModels();
    }
  }

  async function switchModel(filename) {
    if (!filename || modelSwitching()) return;
    modelRequest = true;
    modelActionError = null;
    ++modelFetch;
    renderModels();
    try {
      const response = await fetch("/api/models", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ model: filename }) });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "HTTP " + response.status);
      modelState = data;
      $("#modelMenu").open = false;
      $("#chipLlm").focus();
    } catch (e) {
      modelActionError = e.message;
    } finally {
      modelRequest = false;
      renderModels();
      loadModels();
    }
  }

  async function pollModels() {
    if (!modelRequest) await loadModels();
    setTimeout(pollModels, modelSwitching() ? 1000 : 3000);
  }

  async function loadStatus() {
    try {
      status = await api("/api/status");
    } catch (e) { status = null; }
    renderModelChip();
    renderLibraries();
  }

  async function loadGuides() {
    guides = await api("/api/guides?lang=" + lang);
    const toc = $("#toc");
    toc.innerHTML = "";
    guides.forEach((g, idx) => {
      const d = document.createElement("details");
      const num = g.extra ? "+" : String(idx).padStart(2, "0");
      d.innerHTML = `<summary data-guide="${esc(g.id)}"><span class="n">${num}</span><span>${esc(g.title)}</span></summary>` +
        g.sections.map((s) => `<a href="#" data-guide="${esc(g.id)}" data-anchor="${esc(s.anchor)}">${esc(s.title)}</a>`).join("");
      toc.appendChild(d);
    });
  }

  // ---------------- guides ----------------
  async function openGuide(id, anchor) {
    const data = await api(`/api/guide?lang=${lang}&id=${encodeURIComponent(id)}`);
    const doc = $("#doc");
    doc.className = "doc md";
    doc.innerHTML = md(data.markdown);
    $("#chatView").classList.add("hidden");
    $("#guideView").classList.remove("hidden");
    closeSide();
    window.history.replaceState(null, "", `?lang=${lang}#${encodeURIComponent(id)}${anchor ? "/" + encodeURIComponent(anchor) : ""}`);
    requestAnimationFrame(() => {
      const el = anchor && document.getElementById(anchor);
      if (el) { el.scrollIntoView({ block: "start" }); el.classList.add("flash"); }
      else doc.scrollTop = 0;
    });
  }
  function showChat() {
    $("#guideView").classList.add("hidden");
    $("#chatView").classList.remove("hidden");
    window.history.replaceState(null, "", `?lang=${lang}`);
    closeSide();
    $("#q").focus();
  }

  // ---------------- chat ----------------
  function addMsg(role, html) {
    const w = document.createElement("div");
    w.className = "msg " + role;
    w.innerHTML = `<div class="bubble">${html}</div>`;
    $("#chat").appendChild(w);
    w.scrollIntoView({ block: "end" });
    return w;
  }

  function retrievalLabel(code) {
    if (code === "no_selection") code = "none_selected";
    const labels = {
      en: {success: "searched", zero_hits: "no matches", no_relevant_passage: "no relevant passage", disabled: "disabled", none_selected: "none selected", catalog_error: "catalog unavailable", identity_error: "archive unavailable", http_error: "search failed", parse_error: "invalid response", timeout: "timed out", not_searched_budget: "not searched: request limit", index_needed: "PDF index needed", indexed: "indexed", partially_indexed: "partially indexed", browse_only: "browse only", unsupported_index: "index unavailable", context_budget: "Context limit", context_chars: "Context limit", token_budget: "Model context limit", conflict_unresolved: "Unresolved disagreement", reviewed_precedence: "Superseded by reviewed policy"},
      pt: {success: "pesquisada", zero_hits: "sem resultados", no_relevant_passage: "sem trecho relevante", disabled: "desativada", none_selected: "nenhuma selecionada", catalog_error: "catálogo indisponível", identity_error: "arquivo indisponível", http_error: "falha na busca", parse_error: "resposta inválida", timeout: "tempo esgotado", not_searched_budget: "não pesquisada: limite", index_needed: "PDF precisa de índice", indexed: "indexada", partially_indexed: "parcialmente indexada", browse_only: "somente leitura", unsupported_index: "índice indisponível", context_budget: "Limite de contexto", context_chars: "Limite de contexto", token_budget: "Limite do modelo", conflict_unresolved: "Divergência não resolvida", reviewed_precedence: "Substituído por revisão"},
      es: {success: "buscada", zero_hits: "sin resultados", no_relevant_passage: "sin pasaje relevante", disabled: "desactivada", none_selected: "ninguna seleccionada", catalog_error: "catálogo no disponible", identity_error: "archivo no disponible", http_error: "falló la búsqueda", parse_error: "respuesta inválida", timeout: "tiempo agotado", not_searched_budget: "sin buscar: límite", index_needed: "PDF necesita índice", indexed: "indexada", partially_indexed: "parcialmente indexada", browse_only: "solo lectura", unsupported_index: "índice no disponible", context_budget: "Límite de contexto", context_chars: "Límite de contexto", token_budget: "Límite del modelo", conflict_unresolved: "Desacuerdo no resuelto", reviewed_precedence: "Sustituido por revisión"},
    };
    return (labels[lang] || labels.en)[code] || ({en:"Unavailable",pt:"Indisponível",es:"No disponible"}[lang]);
  }

  function retrievalSummary(report, sources = null) {
    const words = {
      en: {used:"Library passages used", libraries:"Libraries", conflict:"Sources disagree; contested advice withheld.", reviewed:"Reviewed source correction", snapshot:"snapshot"},
      pt: {used:"Trechos de bibliotecas usados", libraries:"Bibliotecas", conflict:"As fontes divergem; orientação contestada omitida.", reviewed:"Correção de fonte revisada", snapshot:"arquivo"},
      es: {used:"Pasajes de bibliotecas usados", libraries:"Bibliotecas", conflict:"Las fuentes discrepan; consejo en disputa omitido.", reviewed:"Corrección de fuente revisada", snapshot:"archivo"},
    }[lang];
    const lines = [];
    const outcome = {en:{failed:"Retrieval failed",partial:"Retrieval partially completed",fetch:"Article fetch failures",skipped:"Articles not fetched"},pt:{failed:"Falha na recuperação",partial:"Recuperação parcial",fetch:"Falhas ao buscar artigos",skipped:"Artigos não obtidos"},es:{failed:"Falló la recuperación",partial:"Recuperación parcial",fetch:"Fallos al obtener artículos",skipped:"Artículos no obtenidos"}}[lang];
    if (["failed", "partial"].includes(report.status)) lines.push(outcome[report.status]);
    const fetchFailures = (report.fetches || []).filter(f => !["success", "rejected", "empty_content", "not_fetched_budget"].includes(f.status)).length;
    if (fetchFailures) lines.push(outcome.fetch + ": " + fetchFailures);
    if (report.not_fetched_budget) lines.push(outcome.skipped + ": " + report.not_fetched_budget);
    if (report.status === "zero_hits" && (report.libraries || []).some(library => library.hits > 0)) lines.push(retrievalLabel("no_relevant_passage"));
    if (sources !== null) lines.push(words.used + ": " + sources.filter(s => s.kind === "kiwix" && !s.context_omitted).length);
    for (const library of report.libraries || []) {
      let line = library.name + ": " + retrievalLabel(library.status);
      if (library.index && library.index.state !== "not_applicable") line += " · " + retrievalLabel(library.index.state);
      lines.push(line);
    }
    if (!(report.libraries || []).length && report.status) lines.push(words.libraries + ": " + retrievalLabel(report.status));
    for (const conflict of report.conflicts || []) lines.push((conflict.resolution === "unresolved" ? words.conflict : words.reviewed) + " " + (conflict.explanation || ""));
    return lines.join("\n");
  }

  function renderRetrieval(container, report, sources = null) {
    if (!report) return;
    let box = container.querySelector(".retrieval-status");
    if (!box) {
      box = document.createElement("details");
      box.className = "retrieval-status";
      container.appendChild(box);
    }
    const label = {en:"Source search and coverage",pt:"Busca e cobertura das fontes",es:"Búsqueda y cobertura de fuentes"}[lang];
    box.open = (report.conflicts || []).some(c => c.resolution === "unresolved");
    box.innerHTML = `<summary>${label}</summary><div>${esc(retrievalSummary(report, sources)).replace(/\n/g, "<br>")}</div>`;
  }

  let sourceSequence = 0;
  const sourceScopes = new WeakMap();
  function renderSources(container, sources) {
    container.querySelector?.('.sources')?.remove();
    if (!sources || !sources.length) return;
    const box = document.createElement("div");
    box.className = "sources";
    if (!sourceScopes.has(container)) sourceScopes.set(container, ++sourceSequence);
    const scope = sourceScopes.get(container);
    const render = (s) => {
      let label = esc(s.doc_title) + " › " + esc(s.section);
      if (s.issued) label += " · " + ({en:"Snapshot",pt:"Arquivo",es:"Archivo"}[lang]) + ": " + esc(s.issued.slice(0, 10));
      if (s.context_omitted) label += " · " + esc(retrievalLabel(s.context_omitted_reason || s.omission_reason || "context_budget"));
      if (s.kind === "guidance") {
        const tag = s.fallback_evidence
          ? {en:"Fallback evidence",pt:"Fonte da orientação alternativa",es:"Fuente de orientación alternativa"}[lang]
          : {en:"Source-backed guidance",pt:"Orientação baseada em fontes",es:"Orientación basada en fuentes"}[lang];
        const publisher = /^https:\/\//i.test(s.url || "")
          ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.doc_title)}</a>` : "";
        return `<details class="src" id="src-${scope}-${s.n}" data-source-number="${s.n}"><summary>[${s.n}] ${label} · ${tag}</summary><p>${esc(s.original_text || s.text)}</p>${publisher}</details>`;
      }
      if (s.kind === "kiwix") {
        return `<a class="src" id="src-${scope}-${s.n}" data-source-number="${s.n}" href="/kiwix${esc(s.link)}" target="_blank" rel="noopener"><span class="num">[${s.n}]</span><span>${label}</span><span class="tag">${t("kiwix")}</span></a>`;
      }
      return `<a class="src" id="src-${scope}-${s.n}" data-source-number="${s.n}" href="#" data-guide="${esc(s.doc_id)}" data-anchor="${esc(s.anchor)}"><span class="num">[${s.n}]</span><span>${label}</span><span class="tag">${t("kit")}</span></a>`;
    };
    const included = sources.filter(s => !s.context_omitted).map(render).join("");
    const omitted = sources.filter(s => s.context_omitted).map(render).join("");
    const notUsed = {en:"Not used in this answer",pt:"Não usadas nesta resposta",es:"No usadas en esta respuesta"}[lang];
    box.innerHTML = `<h4>${t("sources")}</h4>` + included + (omitted ? `<details><summary>${notUsed}</summary>${omitted}</details>` : "");
    container.appendChild(box);
  }

  function updateChat(update) {
    const chat = $("#chat");
    const follow = chat.scrollHeight - chat.clientHeight - chat.scrollTop <= 80;
    update();
    if (follow) chat.scrollTop = chat.scrollHeight;
  }

  function createStreamRenderer(out) {
    let frame = null, pending = null;
    const render = () => {
      frame = null;
      if (pending === null) return;
      const text = pending;
      pending = null;
      updateChat(() => { out.innerHTML = md(text, { cites: true }); });
    };
    return {
      schedule(text) {
        pending = text;
        if (frame === null) frame = requestAnimationFrame(render);
      },
      flush() {
        if (frame !== null) cancelAnimationFrame(frame);
        render();
      },
    };
  }

  async function ask(question) {
    if (busy || modelSwitching() || !question.trim()) return;
    busy = true;
    $("#send").disabled = true;
    $("#welcome") && $("#welcome").remove();
    addMsg("user", esc(question));
    const w = addMsg("ai", `<div class="md typing">${t("thinking")}</div>`);
    const body = w.querySelector(".bubble");
    const out = body.querySelector(".md");
    const renderer = createStreamRenderer(out);
    let text = "", sources = [], started = false, retrieval = null;
    const t0 = Date.now();
    try {
      const resp = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ q: question, lang, history: chatHistory, use_kiwix: $("#useKiwix").checked,
          kiwix_books: librarySelection }),
      });
      if (!resp.ok || !resp.body) throw new Error("HTTP " + resp.status);
      const reader = resp.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      let info = {};
      let completed = false;
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf("\n\n")) >= 0) {
          const block = buf.slice(0, idx); buf = buf.slice(idx + 2);
          const ev = (block.match(/^event: (.*)$/m) || [])[1];
          const dataLine = (block.match(/^data: (.*)$/m) || [])[1];
          if (!ev || dataLine === undefined) continue;
          const data = JSON.parse(dataLine);
          if (ev === "retrieval") { retrieval = data; updateChat(() => renderRetrieval(body, retrieval)); }
          else if (ev === "sources") { sources = data; updateChat(() => { renderSources(body, sources); if (retrieval) renderRetrieval(body, retrieval, sources); }); }
          else if (ev === "token") {
            if (!started) { started = true; text = ""; }
            text += data;
            renderer.schedule(text);
          } else if (ev === "done") { info = data; completed = true; renderer.flush(); if (info.retrieval) updateChat(() => renderRetrieval(body, info.retrieval, sources)); }
          else if (ev === "error") throw new Error(data.error);
        }
      }
      if (!completed) {
        const notice = {
          en: "Interrupted response: the answer may be incomplete.",
          pt: "Resposta interrompida: a resposta pode estar incompleta.",
          es: "Respuesta interrumpida: la respuesta puede estar incompleta.",
        }[lang];
        text += "\n\n**" + notice + "**";
        renderer.schedule(text);
      }
      renderer.flush();
      out.classList.remove("typing");
      updateChat(() => renderSources(body, sources));
      const meta = document.createElement("div");
      meta.className = "meta";
      const secs = info.seconds ?? ((Date.now() - t0) / 1000).toFixed(1);
      const modeKey = info.mode === "llm"
        ? (info.sources_supplied !== true ? "modeUngrounded" : "modeLlm")
        : (info.reason === "ai_disabled" ? "modeDisabled"
          : info.reason === "generation_failed" ? "modeFailed" : "modeSearch");
      const modeLabel = info.mode === "fallback"
        ? {en:"Source-backed fallback",pt:"Orientação alternativa baseada em fontes",es:"Orientación alternativa basada en fuentes"}[lang]
        : t(modeKey);
      meta.textContent = (completed ? modeLabel + " · " : "") + secs + "s";
      updateChat(() => body.appendChild(meta));
      chatHistory.push({ role: "user", content: question }, { role: "assistant", content: text });
      chatHistory = chatHistory.slice(-8);
    } catch (e) {
      out.classList.remove("typing");
      renderer.flush();
      if (!started) out.textContent = "";
      const error = document.createElement("p");
      error.className = "stream-error";
      error.textContent = t("error") + e.message;
      updateChat(() => out.appendChild(error));
    } finally {
      busy = false;
      renderModels();
    }
  }

  // ---------------- sidebar search ----------------
  let searchTimer;
  async function sideSearch(q) {
    const box = $("#searchResults");
    if (!q.trim()) { box.innerHTML = ""; return; }
    const res = await api(`/api/search?lang=${lang}&k=8&q=${encodeURIComponent(q)}`);
    box.innerHTML = res.length
      ? res.map((r) => `<a href="#" data-guide="${esc(r.doc_id)}" data-anchor="${esc(r.anchor)}">${esc(r.section)}<small>${esc(r.doc_title)}</small></a>`).join("")
      : `<small style="color:var(--muted);padding:8px;display:block">${t("noResults")}</small>`;
  }

  // ---------------- language ----------------
  function applyLang() {
    document.documentElement.lang = lang === "pt" ? "pt-BR" : lang;
    document.title = t("title");
    document.querySelectorAll("[data-i18n]").forEach((el) => (el.textContent = t(el.dataset.i18n)));
    document.querySelectorAll("[data-i18n-ph]").forEach((el) => (el.placeholder = t(el.dataset.i18nPh)));
    document.querySelectorAll("[data-i18n-aria]").forEach((el) => el.setAttribute("aria-label", t(el.dataset.i18nAria)));
    document.querySelectorAll(".langs button").forEach((b) => b.classList.toggle("active", b.dataset.lang === lang));
    const quick = $("#quick");
    if (quick) quick.innerHTML = t("quick").map(([k, q]) => `<button data-q="${esc(q)}"><b>${esc(k)}</b>${esc(q)}</button>`).join("");
    renderModels();
    renderLibraries();
  }
  async function setLang(l) {
    lang = l; store("lang", l);
    applyLang();
    await loadGuides();
    loadStatus();
    if (!$("#guideView").classList.contains("hidden")) showChat();
  }

  // ---------------- mobile menu ----------------
  function openSide() { $("#side").classList.add("open"); $("#scrim").classList.add("open"); }
  function closeSide() { $("#side").classList.remove("open"); $("#scrim").classList.remove("open"); }

  // ---------------- events ----------------
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#modelMenu")) $("#modelMenu").open = false;
    if (!e.target.closest("#libraryMenu")) $("#libraryMenu").open = false;
    if (e.target.closest("#chipLlm, #chipKiwix")) closeSide();
    const model = e.target.closest("[data-model-file]");
    if (model) {
      if (!model.disabled) switchModel(model.dataset.modelFile);
      return;
    }
    const g = e.target.closest("[data-guide]");
    if (g) {
      if (g.tagName === "SUMMARY") { openGuide(g.dataset.guide); return; }
      e.preventDefault(); openGuide(g.dataset.guide, g.dataset.anchor); return;
    }
    const c = e.target.closest("[data-cite]");
    if (c) {
      e.preventDefault();
      const src = c.closest(".bubble").querySelector(`[data-source-number="${c.dataset.cite}"]`);
      if (src) { src.scrollIntoView({ block: "center" }); src.classList.add("flash"); setTimeout(() => src.classList.remove("flash"), 1700); }
      return;
    }
    const q = e.target.closest("[data-q]");
    if (q) { ask(q.dataset.q); return; }
    const lb = e.target.closest("[data-lang]");
    if (lb) { setLang(lb.dataset.lang); }
  });
  $("#composer").addEventListener("submit", (e) => {
    e.preventDefault();
    if (busy || modelSwitching()) return;
    const q = $("#q").value;
    $("#q").value = ""; autoGrow();
    ask(q);
  });
  $("#q").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#composer").requestSubmit(); }
  });
  function autoGrow() { const ta = $("#q"); ta.style.height = "auto"; ta.style.height = Math.min(ta.scrollHeight, 200) + "px"; }
  $("#q").addEventListener("input", autoGrow);
  $("#filter").addEventListener("input", (e) => { clearTimeout(searchTimer); searchTimer = setTimeout(() => sideSearch(e.target.value), 180); });
  $("#askBtn").addEventListener("click", showChat);
  $("#homeLink").addEventListener("click", (e) => { e.preventDefault(); showChat(); });
  $("#backBtn").addEventListener("click", showChat);
  $("#printBtn").addEventListener("click", () => window.print());
  $("#menuBtn").addEventListener("click", openSide);
  $("#scrim").addEventListener("click", closeSide);
  $("#useKiwix").checked = store("kiwix") !== "0";
  $("#useKiwix").addEventListener("change", (e) => {
    store("kiwix", e.target.checked ? "1" : "0");
    renderLibraries();
  });
  $("#libraryAll").addEventListener("change", (e) => saveLibraries(e.target.checked ? null : []));
  $("#libraryOptions").addEventListener("change", () => {
    const selected = Array.from($("#libraryOptions").querySelectorAll("input:checked"), (box) => box.dataset.library);
    saveLibraries(selected.length === libraryBooks().length ? null : selected);
  });
  window.addEventListener("storage", (e) => {
    if (e.key === "ias:libraries" || e.key === null) {
      librarySelection = readLibrarySelection();
      renderLibraries();
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && $("#libraryMenu").open) {
      $("#libraryMenu").open = false;
      $("#chipKiwix").focus();
    }
    if (e.key === "Escape" && $("#modelMenu").open) {
      $("#modelMenu").open = false;
      $("#chipLlm").focus();
    }
  });

  // ---------------- initialization ----------------
  applyLang();
  loadGuides().then(() => {
    let h;
    try { h = decodeURIComponent(location.hash.slice(1)); } catch (e) { return; }
    // Match the longest document ID, including legacy unescaped nested bookmarks.
    const guide = guides.filter((g) => h === g.id || h.startsWith(g.id + "/"))
      .sort((a, b) => b.id.length - a.id.length)[0];
    if (guide) openGuide(guide.id, h.slice(guide.id.length + 1));
  });
  loadStatus();
  pollModels();
  setInterval(loadStatus, 20000);
})();
