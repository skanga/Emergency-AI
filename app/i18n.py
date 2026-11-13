"""Server-side prompts and messages in English, Portuguese and Spanish."""

SYSTEM_PROMPT = {
    "pt": (
        "Você é a Emergency AI, um assistente offline que ajuda pessoas a sobreviver "
        "quando a internet e os serviços estão fora do ar. Responda SEMPRE em português do Brasil, "
        "de forma clara, prática e em passos numerados quando fizer sentido.\n"
        "Regras:\n"
        "1. Baseie a resposta nas FONTES fornecidas. Cite-as no texto com o número entre colchetes, ex.: [1], [2].\n"
        "2. Se as fontes não cobrirem a pergunta, diga isso claramente e dê apenas orientações gerais e seguras, "
        "avisando que não há fonte no kit.\n"
        "3. Em temas de saúde: inclua sinais de alerta e quando procurar ajuda profissional; nunca invente doses de "
        "remédios — remeta à bula ou ao profissional; lembre que a orientação não substitui um médico.\n"
        "4. Priorize a segurança (fogo, química, eletricidade, monóxido de carbono).\n"
        "5. Seja objetivo. Nada de introduções longas."
    ),
    "en": (
        "You are Emergency AI, an offline assistant that helps people survive when the internet and "
        "services are down. ALWAYS answer in English, clearly and practically, using numbered steps when useful.\n"
        "Rules:\n"
        "1. Base your answer on the SOURCES provided. Cite them inline with the number in brackets, e.g. [1], [2].\n"
        "2. If the sources do not cover the question, say so clearly and give only general, safe guidance, "
        "noting there is no source in the kit.\n"
        "3. For health topics: include warning signs and when to seek professional help; never invent drug "
        "doses — refer to the label or a professional; remind that this does not replace a doctor.\n"
        "4. Prioritize safety (fire, chemicals, electricity, carbon monoxide).\n"
        "5. Be concise. No long introductions."
    ),
    "es": (
        "Eres la Emergency AI, un asistente offline que ayuda a las personas a sobrevivir cuando "
        "internet y los servicios no funcionan. Responde SIEMPRE en español, de forma clara y práctica, con "
        "pasos numerados cuando sea útil.\n"
        "Reglas:\n"
        "1. Basa la respuesta en las FUENTES proporcionadas. Cítalas en el texto con el número entre corchetes, p. ej. [1], [2].\n"
        "2. Si las fuentes no cubren la pregunta, dilo claramente y da solo orientaciones generales y seguras, "
        "avisando que no hay fuente en el kit.\n"
        "3. En temas de salud: incluye señales de alarma y cuándo buscar ayuda profesional; nunca inventes dosis "
        "de medicamentos — remite al prospecto o a un profesional; recuerda que esto no reemplaza a un médico.\n"
        "4. Prioriza la seguridad (fuego, químicos, electricidad, monóxido de carbono).\n"
        "5. Sé conciso. Sin introducciones largas."
    ),
}

SOURCES_HEADER = {"pt": "FONTES", "en": "SOURCES", "es": "FUENTES"}
QUESTION_HEADER = {"pt": "PERGUNTA", "en": "QUESTION", "es": "PREGUNTA"}

NO_LLM_NOTE = {
    "pt": "**Modo sem IA generativa** (nenhum modelo de linguagem ativo). Estes são os trechos mais relevantes do kit para a sua pergunta:",
    "en": "**Search-only mode** (no language model running). These are the most relevant passages in the kit for your question:",
    "es": "**Modo sin IA generativa** (ningún modelo de lenguaje activo). Estos son los fragmentos más relevantes del kit para tu pregunta:",
}

NO_RESULTS = {
    "pt": "Não encontrei nada no kit sobre isso. Tente outras palavras (ex.: \"purificar água\", \"queimadura\", \"fazer fogo\").",
    "en": "I found nothing in the kit about that. Try other words (e.g. \"purify water\", \"burn\", \"make fire\").",
    "es": "No encontré nada en el kit sobre eso. Prueba otras palabras (p. ej. \"purificar agua\", \"quemadura\", \"hacer fuego\").",
}

LLM_ERROR = {
    "pt": "\n\n_(O modelo de linguagem falhou: {err}. Mostrando os trechos encontrados.)_\n\n",
    "en": "\n\n_(The language model failed: {err}. Showing the passages found.)_\n\n",
    "es": "\n\n_(El modelo de lenguaje falló: {err}. Mostrando los fragmentos encontrados.)_\n\n",
}

MEDICAL_FOOTER = {
    "pt": "\n\n> ⚠️ Orientação de primeiros socorros, não substitui atendimento médico. Havendo socorro disponível, procure-o.",
    "en": "\n\n> ⚠️ First-aid guidance only; it does not replace medical care. If help is available, seek it.",
    "es": "\n\n> ⚠️ Orientación de primeros auxilios; no reemplaza la atención médica. Si hay ayuda disponible, búscala.",
}

KIWIX_LABEL = {"pt": "Biblioteca offline (Kiwix)", "en": "Offline library (Kiwix)", "es": "Biblioteca offline (Kiwix)"}
KIT_LABEL = {"pt": "Guia do kit", "en": "Kit guide", "es": "Guía del kit"}

MEDICAL_WORDS = (
    "sangr", "ferid", "queim", "fratur", "rcp", "infart", "parada", "febre", "diarr", "vomit", "remed",
    "medic", "dose", "picad", "cobra", "escorp", "alerg", "engasg", "parto", "desidrat", "hipoterm",
    "insola", "infec", "antibi", "dor ", "pressao", "diabet", "convuls", "desmai",
    "bleed", "wound", "burn", "fractur", "cpr", "heart", "fever", "diarrh", "vomit", "medicin", "drug",
    "bite", "snake", "scorpion", "allerg", "chok", "birth", "dehydrat", "hypotherm", "heatstroke",
    "infect", "pain", "seizure", "faint",
    "sangre", "herid", "quemad", "fiebre", "medicament", "mordedura", "serpiente", "alacran", "alergi",
    "atragant", "deshidrat", "hipoterm", "infecc", "dolor", "convulsi", "desmay",
)
SOURCE_FALLBACK_NOTE = {
    "en": "**Source passages**: a complete AI answer is unavailable. Showing the relevant passages instead:",
    "pt": "**Trechos das fontes**: uma resposta completa da IA não está disponível. Mostrando os trechos relevantes:",
    "es": "**Fragmentos de las fuentes**: no hay una respuesta completa de la IA disponible. Se muestran los fragmentos relevantes:",
}

INCOMPLETE_ANSWER = {
    "en": {
        "limit": "\n\n> **Incomplete answer:** generation reached its token limit. Read the linked sources for complete instructions.",
        "interrupted": "\n\n> **Incomplete answer:** the model did not confirm a complete response. Read the linked sources for complete instructions.",
    },
    "pt": {
        "limit": "\n\n> **Resposta incompleta:** a geração atingiu o limite de tokens. Leia as fontes vinculadas para obter instruções completas.",
        "interrupted": "\n\n> **Resposta incompleta:** o modelo não confirmou uma resposta completa. Leia as fontes vinculadas para obter instruções completas.",
    },
    "es": {
        "limit": "\n\n> **Respuesta incompleta:** la generación alcanzó el límite de tokens. Lea las fuentes enlazadas para obtener instrucciones completas.",
        "interrupted": "\n\n> **Respuesta incompleta:** el modelo no confirmó una respuesta completa. Lea las fuentes enlazadas para obtener instrucciones completas.",
    },
}

READ_FULL_SOURCE = {
    "en": "Open the full source below. This section is unavailable or too long to include safely as a complete passage.",
    "pt": "Abra a fonte completa abaixo. Esta seção está indisponível ou é longa demais para ser incluída na íntegra.",
    "es": "Abra la fuente completa abajo. Esta sección no está disponible o es demasiado larga para incluirla completa.",
}
