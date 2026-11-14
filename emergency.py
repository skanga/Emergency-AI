#!/usr/bin/env python3
"""Emergency AI — command-line entry point.

Usage:
  python emergency.py start              # start engines and web interface (default)
  python emergency.py chat               # terminal chat
  python emergency.py ask "question"     # single question in the terminal
  python emergency.py search "terms"     # search the guides
  python emergency.py prepare            # download the model, engines and Kiwix libraries (requires internet)
  python emergency.py status             # show installed and running components

Common options:
--lang en|pt|es
--local-only (turn off local-network sharing)
--port 8090
"""

import os
import sys
import time
import argparse
import threading
import webbrowser

if sys.version_info < (3, 8):
    sys.exit("Python 3.8+ is required.")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure UTF-8 output in older Windows terminals.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from app import __version__  # noqa: E402
from app.config import launcher_command, LANGS, load_settings, platform_key  # noqa: E402

BANNER = r"""
  +-------------------------------------------------------------+
  |                         EMERGENCY AI                        |
  | Offline knowledge and assistance when the internet is down. |
  +-------------------------------------------------------------+
"""

MSG = {
    "pt": {"open": "Abra no navegador:", "lan": "Outros aparelhos da rede podem acessar:", "stop": "Pressione Ctrl+C para encerrar.",
           "bye": "Encerrando…", "you": "Você", "ai": "IA", "exit": "(digite 'sair' para encerrar)", "src": "Fontes",
           "mode_llm": "modelo", "mode_search": "busca (sem IA generativa)", "starting": "Iniciando…"},
    "en": {"open": "Open in your browser:", "lan": "Other devices on the network can use:", "stop": "Press Ctrl+C to stop.",
           "bye": "Shutting down…", "you": "You", "ai": "AI", "exit": "(type 'exit' to quit)", "src": "Sources",
           "mode_llm": "model", "mode_search": "search (no generative AI)", "starting": "Starting…"},
    "es": {"open": "Abre en el navegador:", "lan": "Otros dispositivos de la red pueden acceder:", "stop": "Pulsa Ctrl+C para salir.",
           "bye": "Cerrando…", "you": "Tú", "ai": "IA", "exit": "(escribe 'salir' para terminar)", "src": "Fuentes",
           "mode_llm": "modelo", "mode_search": "búsqueda (sin IA generativa)", "starting": "Iniciando…"},
}


def lan_ip():
    import socket
    import ipaddress

    def usable(ip):
        addr = ipaddress.ip_address(ip)
        return not (addr.is_loopback or addr.is_unspecified or addr.is_multicast or addr.is_link_local)

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            # UDP connect selects a route; it does not send a packet or require internet.
            sock.connect(("192.0.2.1", 1))
            ip = sock.getsockname()[0]
            if usable(ip):
                return ip
    except OSError:
        pass
    try:
        for result in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = result[4][0]
            if usable(ip):
                return ip
    except OSError:
        pass
    return None


def print_connection_info(host, port, lang, stream=None):
    import ipaddress
    from app.qr import terminal_colors, terminal_qr

    stream = stream or sys.stdout
    m = MSG[lang]
    browser_host = '127.0.0.1' if host in ('0.0.0.0', 'localhost') else host
    print(f"\n  {m['open']}  http://{browser_host}:{port}/?lang={lang}", file=stream)
    ip = lan_ip() if host == '0.0.0.0' else host
    try:
        addr = ipaddress.ip_address(ip) if ip else None
    except ValueError:
        addr = None
    if addr and not (addr.is_loopback or addr.is_unspecified or addr.is_link_local):
        url = f'http://{ip}:{port}/?lang={lang}'
        print(f"  {m['lan']}  {url}", file=stream)
        qr = terminal_qr(url, color=terminal_colors(stream))
        try:
            qr.encode(getattr(stream, 'encoding', None) or 'utf-8')
        except UnicodeEncodeError:
            return  # The clickable URL still works in consoles without block characters.
        print(qr, file=stream)


def cmd_start(args, settings):
    from app.engine import Engine
    from app.models import ModelManager
    from app.launcher import Launcher, port_in_use
    from app.net import open_url
    from app.server import serve
    from app.startup import ensure_ready

    host = args.host or settings.get("web_host", "0.0.0.0")
    port = args.port if args.port is not None else settings.get("web_port", 8090)
    browser_host = "127.0.0.1" if host in ("0.0.0.0", "localhost") else host
    url = f"http://{browser_host}:{port}/?lang={args.lang}"
    if port and port_in_use(int(port), browser_host):
        try:
            with open_url(url, timeout=2) as response:
                ours = response.headers.get("Server", "").startswith("Emergency-AI/")
                running_host = response.headers.get('X-Emergency-AI-Bind', '127.0.0.1')
        except Exception:
            ours = False
        if not ours:
            print(f"Port {port} is occupied by another service. Use 'start --port <number>'.")
            return 1
        if running_host != ('127.0.0.1' if host == 'localhost' else host):
            print("The running server uses a different network binding. Stop it with Ctrl+C in its console,")
            print("then restart with the requested sharing option (or choose a different --port).")
            return 1
        print(f"UI already running: {url}")
        print_connection_info(running_host, port, args.lang)
        if settings.get("open_browser", True) and not args.no_browser:
            webbrowser.open(url)
        return 0

    m = MSG[args.lang]
    print(BANNER)
    print(f"  v{__version__} — {platform_key()}\n")
    print(m["starting"])
    report = ensure_ready(settings, args.lang) if not args.no_engines else {}
    launcher = Launcher(settings)
    if not args.no_engines:
        if not report.get("external_llm") and settings.get("llm_backend", "auto") in ("auto", "llamacpp", "openai"):
            launcher.start_llm()
        if not report.get("external_kiwix"):
            launcher.start_kiwix()
    engine = Engine(settings)
    models = ModelManager(engine, launcher, enabled=not args.no_engines and not report.get("external_llm"))
    try:
        httpd = serve(engine, settings, host, port, models=models)
    except OSError as e:
        print(f"Unable to open the app on {host}:{port}: {e}")
        launcher.stop()
        return 1
    port = httpd.server_address[1]
    url = f"http://{browser_host}:{port}/?lang={args.lang}"
    print_connection_info(httpd.server_address[0], port, args.lang)
    print(f"  {m['stop']}\n")
    if settings.get("open_browser", True) and not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n" + m["bye"])
    finally:
        httpd.server_close()
        models.close()
        launcher.stop()


def _print_answer(engine, question, lang, history):
    m = MSG[lang]
    sys.stdout.write(f"\n{m['ai']}: ")
    sys.stdout.flush()
    text, sources, info = [], [], {}
    for kind, data in engine.answer(question, lang, history=history):
        if kind == "sources":
            sources = data
        elif kind == "token":
            text.append(data)
            sys.stdout.write(data)
            sys.stdout.flush()
        elif kind == "done":
            info = data
    if sources:
        print(f"\n\n{m['src']}:")
        for s in sources:
            where = s.get("link") or f"knowledge/{s['lang']}/{s['doc_id']}.md#{s['anchor']}"
            print(f"  [{s['n']}] {s['doc_title']} › {s['section']}  ({where})")
    mode = m["mode_llm"] if info.get("mode") == "llm" else m["mode_search"]
    print(f"  — {mode}, {info.get('seconds', 0)}s\n")
    return "".join(text)


def _engine_with_launcher(args, settings):
    from app.engine import Engine
    from app.launcher import Launcher
    launcher = Launcher(settings, say=lambda *_: None)
    if not args.no_engines:
        started = launcher.start_llm()
        launcher.start_kiwix()
        engine = Engine(settings)
        if started and launcher.procs:
            for _ in range(90):  # wait for the model to load
                if engine.llm(force=True):
                    break
                time.sleep(1)
    else:
        engine = Engine(settings)
    return engine, launcher


def cmd_chat(args, settings):
    m = MSG[args.lang]
    engine, launcher = _engine_with_launcher(args, settings)
    print(BANNER)
    print(m["exit"])
    history = []
    try:
        while True:
            try:
                q = input(f"\n{m['you']}: ").strip()
            except EOFError:
                break
            if q.lower() in ("sair", "exit", "quit", "salir"):
                break
            if not q:
                continue
            ans = _print_answer(engine, q, args.lang, history)
            history += [{"role": "user", "content": q}, {"role": "assistant", "content": ans}]
            history = history[-8:]
    except KeyboardInterrupt:
        pass
    finally:
        launcher.stop()


def cmd_ask(args, settings):
    engine, launcher = _engine_with_launcher(args, settings)
    try:
        _print_answer(engine, " ".join(args.text), args.lang, [])
    finally:
        launcher.stop()


def cmd_search(args, settings):
    from app.knowledge import KnowledgeBase
    kb = KnowledgeBase()
    for score, ch in kb.search(" ".join(args.text), args.lang, k=args.k):
        print(f"[{score:5.2f}] {ch.doc_title} › {ch.section}  (knowledge/{ch.lang}/{ch.doc_id}.md)")
        snippet = ch.text.replace("\n", " ")
        print("        " + (snippet[:220] + "…" if len(snippet) > 220 else snippet))


def cmd_status(args, settings):
    from app.engine import Engine
    from app.launcher import find_kiwix_serve, find_llama_server, find_model, find_zims
    print(f"Emergency AI v{__version__} — {platform_key()}")
    from app.startup import inspect
    report = inspect(settings)
    print("  Setup state: " + report["state"].replace("_", " "))
    for item in report["missing"]:
        print("  Missing: " + item)
    if report["state"] in ("first_run", "incomplete"):
        print(f"  Included guides remain available. Use '{launcher_command()} prepare' to configure or '--resume' to repair.")
    binary, kind = find_llama_server()
    print(f"  AI engine ({kind or 'llama.cpp'}): {binary or '—'}")
    print(f"  Model: {find_model(settings) or '—'}")
    print(f"  kiwix-serve: {find_kiwix_serve() or '—'}")
    zims = find_zims()
    print(f"  ZIM libraries: {len(zims)}")
    for z in zims:
        print(f"    - {os.path.basename(z)}  ({os.path.getsize(z) / 1024 ** 3:.2f} GB)")
    st = Engine(settings).status()
    print(f"  Active AI: {st['llm'] or 'no (search mode)'}")
    print(f"  Active Kiwix: {'yes' if st['kiwix'] else 'no'}")
    for lang, s in st["knowledge"].items():
        print(f"  Guides [{lang}]: {s['docs']} documents, {s['chunks']} passages")


def cmd_prepare(args, settings):
    from app import prepare
    try:
        return prepare.run(lang=args.lang, model=args.model, zims=args.zims, oses=args.os, python=args.python,
                           yes=args.yes, search=args.search, skip_tools=args.skip_tools, archives=args.archives,
                           resume=args.resume)
    except (ValueError, OSError) as e:
        print(f"Preparation failed: {e}", file=sys.stderr)
        return 1


def main():
    settings = load_settings()
    p = argparse.ArgumentParser(description="Emergency AI — offline knowledge and assistance when services go down")
    p.add_argument("--lang", choices=LANGS, default=settings.get("language", "en"))
    p.add_argument("--no-engines", action="store_true", help="do not start llama.cpp/kiwix-serve")
    sub = p.add_subparsers(dest="cmd")

    s = sub.add_parser("start", help="web interface")
    sharing = s.add_mutually_exclusive_group()
    sharing.add_argument("--host", help="address to bind (default: all local-network interfaces)")
    sharing.add_argument("--local-only", dest="host", action="store_const", const="127.0.0.1",
                         help="turn off local-network sharing; use this computer only")
    s.add_argument("--port", type=int)
    s.add_argument("--no-browser", action="store_true")

    sub.add_parser("chat", help="terminal chat")
    a = sub.add_parser("ask", help="single question")
    a.add_argument("text", nargs="+")
    se = sub.add_parser("search", help="search the guides")
    se.add_argument("text", nargs="+")
    se.add_argument("-k", type=int, default=5)
    sub.add_parser("status", help="show installed components")

    pr = sub.add_parser("prepare", help="download model, engines and libraries (requires internet)")
    pr.add_argument("--model", help="model ID in config/models.json or 'none'")
    pr.add_argument("--zims", help="minimal | recommended | full | none")
    pr.add_argument("--archives", help="optional OLD snapshots: none (default) | all | comma-separated IDs: "
                    "wikem, wikihow-en, wikihow-es, wikihow-pt; see README for dates and sizes")
    pr.add_argument("--os", help="this | all | comma-separated list (e.g. windows-x86_64,macos-arm64)")
    pr.add_argument("--python", action="store_true", default=None, help="include portable Python")
    pr.add_argument("--yes", action="store_true", help="skip prompts (use defaults)")
    pr.add_argument("--search", help="search the Kiwix library catalog")
    pr.add_argument("--skip-tools", action="store_true", help="download only the model and ZIMs")
    pr.add_argument("--resume", action="store_true", help="reuse saved choices; repair this platform by default")

    # Launchers forward arguments unchanged; no subcommand means start.
    argv = sys.argv[1:]
    cmds = ("start", "chat", "ask", "search", "status", "prepare")
    pos = next((i for i, a in enumerate(argv) if a in cmds), None)
    if pos:
        argv = [argv[pos]] + argv[:pos] + argv[pos + 1:]
    elif pos is None and not any(a in ("-h", "--help") for a in argv):
        argv = ["start"] + argv
    for token in list(argv):
        if token.startswith("--lang="):
            argv.remove(token)
            argv.insert(0, token)
    if "--lang" in argv:
        i = argv.index("--lang")
        if i + 1 < len(argv):
            lang = argv[i + 1]
            argv = argv[:i] + argv[i + 2:]
            argv = ["--lang", lang] + argv
    for flag in ("--no-engines",):
        if flag in argv:
            argv.remove(flag)
            argv.insert(0, flag)
    args = p.parse_args(argv)
    if args.lang != settings.get("language"):
        settings["language"] = args.lang

    cmd = args.cmd or "start"
    if cmd == "start" and not hasattr(args, "host"):
        args.host, args.port, args.no_browser = None, None, False
    return {"start": cmd_start, "chat": cmd_chat, "ask": cmd_ask, "search": cmd_search,
     "status": cmd_status, "prepare": cmd_prepare}[cmd](args, settings)


if __name__ == "__main__":
    sys.exit(main())
