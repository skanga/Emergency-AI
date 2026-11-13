"""Local knowledge base: load Markdown guides, split into passages and search with BM25.

No external dependencies. Also index extra documents (.md / .txt) placed in
knowledge/extra/ — they appear in searches in every language.
"""

import math
import os
import re
import unicodedata
from collections import Counter

from .config import KNOWLEDGE_DIR, LANGS

STOPWORDS = set(
    """
    a o as os um uma uns umas de do da dos das no na nos nas em por para com sem sob sobre que se e ou mas
    como quando onde qual quais quem eu tu ele ela nos vos eles elas meu minha seu sua isso isto aquilo
    esse essa este esta ao aos pelo pela pelos pelas ja nao sim mais menos muito pouco tambem so ser
    estar ter fazer posso pode podemos devo deve vou vai e eh foi sao era ha tem
    the a an of to in on for with without by from and or but how what when where which who is are be
    can could should do does i you he she it we they my your this that these those at as if not no yes
    el la los las un una unos unas del al en por para con sin sobre que se y o pero como cuando donde
    cual quien yo tu el ella nosotros ellos mi su esto eso este esta es son ser estar tener hacer puedo
    puede debo debe voy va hay muy mas menos tambien solo
    """.split()
)

TOKEN_RE = re.compile(r"[a-z0-9]+")

# Simple search synonyms (applied to the question, not the documents).
SYNONYMS = [
    ("offline", "backup", "backups", "dados", "datos", "data", "files", "arquivos", "archivos", "pendrive", "usb", "kiwix"),
    ("information", "informacao", "informacoes", "informacion", "dados", "datos", "data"),
    ("purificar", "desinfetar", "tratar", "potavel", "ferver", "purify", "disinfect", "potable", "boil", "desinfectar", "potable", "hervir"),
    ("sangramento", "hemorragia", "sangrar", "torniquete", "bleeding", "bleed", "tourniquet", "sangrado"),
    ("rcp", "massagem", "cardiaca", "reanimacao", "parada", "cpr", "resuscitation", "reanimacion", "masaje"),
    ("soro", "reidratacao", "sro", "desidratacao", "rehydration", "ors", "dehydration", "suero", "rehidratacion", "deshidratacion"),
    ("fogo", "fogueira", "acender", "isca", "fire", "campfire", "ignite", "tinder", "fuego", "fogata", "encender", "yesca"),
    ("comida", "alimento", "alimentos", "food", "comer", "alimentacion"),
    ("conservar", "preservar", "conservacao", "preserve", "preservation", "conservacion", "guardar"),
    ("alcool", "etanol", "destilar", "destilacao", "fermentar", "alcohol", "ethanol", "distill", "distillation", "ferment", "destilacion"),
    ("queimadura", "queimado", "burn", "burns", "quemadura"),
    ("abrigo", "shelter", "refugio", "barraca", "tent", "carpa"),
    ("frio", "hipotermia", "cold", "hypothermia"),
    ("calor", "insolacao", "heat", "heatstroke", "golpe"),
    ("cobra", "serpente", "snake", "serpiente", "viboras", "ofidico"),
    ("sabao", "soap", "jabon", "lixivia", "lye", "lejia"),
    ("radio", "comunicacao", "communication", "comunicacion"),
    ("plantar", "horta", "cultivo", "sementes", "garden", "seeds", "huerta", "semillas"),
    ("engasgo", "engasgado", "heimlich", "choking", "atragantamiento"),
    ("ferida", "corte", "machucado", "wound", "cut", "herida"),
    ("febre", "fever", "fiebre"),
    ("diarreia", "diarrhea", "diarrea"),
]
_SYN_INDEX = {}


def _build_syn():
    for group in SYNONYMS:
        toks = []
        for w in group:
            t = w[:6] if len(w) > 6 else w
            toks.append(t)
        for t in toks:
            _SYN_INDEX.setdefault(t, set()).update(x for x in toks if x != t)


_build_syn()


def strip_accents(text):
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def tokenize(text):
    """Lowercase, strip accents and stopwords, and stem by prefix (works for PT/ES/EN)."""
    text = strip_accents(text.lower())
    out = []
    for tok in TOKEN_RE.findall(text):
        if tok in STOPWORDS or len(tok) < 2:
            continue
        if not tok.isdigit() and len(tok) > 6:
            tok = tok[:6]
        out.append(tok)
    return out


class Chunk:
    __slots__ = ("id", "lang", "doc_id", "doc_title", "section", "anchor", "text", "tokens", "tf", "length")

    def __init__(self, cid, lang, doc_id, doc_title, section, anchor, text):
        self.id = cid
        self.lang = lang
        self.doc_id = doc_id
        self.doc_title = doc_title
        self.section = section
        self.anchor = anchor
        self.text = text
        # Guide and section titles carry double weight.
        self.tokens = tokenize(f"{doc_title} {section} {section} {text}")
        self.tf = Counter(self.tokens)
        self.length = len(self.tokens)

    def to_dict(self, score=None, max_chars=None):
        text = self.text
        if max_chars and len(text) > max_chars:
            text = text[:max_chars].rsplit(" ", 1)[0] + " …"
        d = {
            "id": self.id,
            "lang": self.lang,
            "doc_id": self.doc_id,
            "doc_title": self.doc_title,
            "section": self.section,
            "anchor": self.anchor,
            "text": text,
            "kind": "kit",
        }
        if score is not None:
            d["score"] = round(score, 3)
        return d


def slugify(text):
    text = strip_accents(text.lower())
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "section"


def split_markdown(md_text):
    """Keep each level-two section intact, including its warnings and references."""
    lines = md_text.splitlines()
    title = ""
    sections = []
    current_title = None
    buf = []

    def flush():
        body = "\n".join(buf).strip()
        if body or current_title:
            sections.append([current_title or title, body])

    for line in lines:
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            flush()
            current_title = line[3:].strip()
            buf = []
        else:
            buf.append(line)
    flush()

    result = []
    for sec_title, body in sections:
        if not body:
            continue
        anchor = slugify(sec_title)
        result.append((sec_title, anchor, body))
    return title, result


class KnowledgeBase:
    K1 = 1.4
    B = 0.75

    def __init__(self, root=KNOWLEDGE_DIR):
        self.root = root
        self.docs = {lang: [] for lang in LANGS}  # lang -> [{id,title,sections}]
        self.raw = {}  # (lang, doc_id) -> markdown
        self.chunks = {lang: [] for lang in LANGS}
        self.df = {lang: Counter() for lang in LANGS}
        self.avgdl = {lang: 1.0 for lang in LANGS}
        self.load()

    # ---------- loading ----------
    def load(self):
        extra = self._load_extra()
        for lang in LANGS:
            folder = os.path.join(self.root, lang)
            files = sorted(f for f in os.listdir(folder) if f.endswith(".md")) if os.path.isdir(folder) else []
            for fname in files:
                doc_id = fname[:-3]
                with open(os.path.join(folder, fname), "r", encoding="utf-8") as f:
                    md = f.read()
                self._add_doc(lang, doc_id, md)
            for doc_id, md in extra:
                self._add_doc(lang, doc_id, md, extra=True)
            chunks = self.chunks[lang]
            for ch in chunks:
                for tok in ch.tf:
                    self.df[lang][tok] += 1
            if chunks:
                self.avgdl[lang] = sum(c.length for c in chunks) / len(chunks)

    def _load_extra(self):
        folder = os.path.join(self.root, "extra")
        out = []
        if not os.path.isdir(folder):
            return out
        for dirpath, _, files in os.walk(folder):
            for fname in sorted(files):
                if not fname.lower().endswith((".md", ".txt")) or fname.lower() == "readme.md":
                    continue
                path = os.path.join(dirpath, fname)
                try:
                    with open(path, "r", encoding="utf-8", errors="replace") as f:
                        text = f.read()
                except OSError:
                    continue
                rel = os.path.relpath(path, folder).replace(os.sep, "/")
                doc_id = "extra/" + rel.rsplit(".", 1)[0]
                if fname.lower().endswith(".txt") or not text.lstrip().startswith("# "):
                    text = f"# {os.path.splitext(fname)[0]}\n\n" + text
                out.append((doc_id, text))
        return out

    def _add_doc(self, lang, doc_id, md, extra=False):
        title, sections = split_markdown(md)
        title = title or doc_id
        self.raw[(lang, doc_id)] = md
        seen = []
        for i, (sec, anchor, text) in enumerate(sections):
            cid = f"{lang}:{doc_id}:{i}"
            self.chunks[lang].append(Chunk(cid, lang, doc_id, title, sec, anchor, text))
            if not seen or seen[-1]["anchor"] != anchor:
                seen.append({"title": sec, "anchor": anchor})
        self.docs[lang].append({"id": doc_id, "title": title, "sections": seen, "extra": extra})

    # ---------- queries ----------
    def list_docs(self, lang):
        return self.docs.get(lang, [])

    def get_doc(self, lang, doc_id):
        return self.raw.get((lang, doc_id))

    def search(self, query, lang="en", k=5):
        lang = lang if lang in self.chunks else "en"
        q_tokens = tokenize(query)
        if not q_tokens:
            return []
        chunks = self.chunks[lang]
        n = len(chunks)
        df = self.df[lang]
        avgdl = self.avgdl[lang]
        q_counts = Counter(q_tokens)
        # Synonyms carry half weight and do not count toward coverage.
        syn_weight = {}
        for tok in list(q_counts):
            for s in _SYN_INDEX.get(tok, ()):
                if s not in q_counts and df.get(s):
                    syn_weight[s] = 0.5
        weights = {t: 1.0 for t in q_counts}
        weights.update(syn_weight)
        scored = []
        for ch in chunks:
            score = 0.0
            section_tokens = set(tokenize(ch.section))
            for tok, w in weights.items():
                f = ch.tf.get(tok)
                if not f:
                    continue
                qtf = q_counts.get(tok, 1)
                idf = math.log(1 + (n - df[tok] + 0.5) / (df[tok] + 0.5))
                denom = f + self.K1 * (1 - self.B + self.B * ch.length / avgdl)
                score += w * idf * (f * (self.K1 + 1)) / denom * (1 + 0.2 * (qtf - 1))
                # A section heading is a stronger topic signal than a body mention.
                if tok in section_tokens:
                    score += 2 * w * idf
            if score > 0:
                # Boost passages containing multiple distinct query terms.
                coverage = sum(1 for t in q_counts if t in ch.tf) / len(q_counts)
                scored.append((score * (0.6 + 0.4 * coverage), ch))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:k]

    def stats(self):
        return {lang: {"docs": len(self.docs[lang]), "chunks": len(self.chunks[lang])} for lang in LANGS}


def best_passages(text, query, max_chars=1500):
    """Select the most relevant paragraphs from a long text (e.g. a Kiwix article)."""
    q = set(tokenize(query))
    paras = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if len(p.strip()) > 40]
    if not paras:
        return text[:max_chars]
    scored = []
    for i, p in enumerate(paras):
        toks = tokenize(p)
        if not toks:
            continue
        hits = sum(1 for t in toks if t in q)
        scored.append((hits / (len(toks) ** 0.5) + (0.3 if i < 2 else 0), i, p))
    scored.sort(reverse=True)
    picked = sorted(scored[:6], key=lambda x: x[1])
    out = ""
    for _, _, p in picked:
        if len(out) + len(p) > max_chars:
            break
        out += p + "\n\n"
    return out.strip() or paras[0][:max_chars]
