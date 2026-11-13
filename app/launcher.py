"""Start the local engines (llama.cpp and kiwix-serve) available in the kit."""

import glob
import os
import shutil
import socket
import subprocess
import sys

from .config import LOG_DIR, MODELS_DIR, RUNTIME_DIR, ZIM_DIR, exe, is_windows, load_json, platform_key, CONFIG_DIR


def port_in_use(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def _find_in(base, names):
    if not os.path.isdir(base):
        return None
    for dirpath, _, files in os.walk(base):
        for n in names:
            if n in files:
                return os.path.join(dirpath, n)
    return None


def find_llama_server():
    plat = platform_key()
    names = [exe("llama-server")]
    found = _find_in(os.path.join(RUNTIME_DIR, "llama.cpp", plat), names)
    if found:
        return found, "llama.cpp"
    # llamafile (one executable for all systems)
    for pattern in ("llamafile*", "llamafile*.exe"):
        for p in sorted(glob.glob(os.path.join(RUNTIME_DIR, pattern))):
            if os.path.isfile(p) and not p.endswith((".gguf", ".zip", ".part")):
                return p, "llamafile"
    which = shutil.which("llama-server")
    if which:
        return which, "llama.cpp"
    return None, None


def find_kiwix_serve():
    plat = platform_key()
    found = _find_in(os.path.join(RUNTIME_DIR, "kiwix-tools", plat), [exe("kiwix-serve")])
    if found:
        return found
    return shutil.which("kiwix-serve")


def find_model(settings):
    files = sorted(glob.glob(os.path.join(MODELS_DIR, "*.gguf")))
    if not files:
        return None
    wanted = settings.get("model_file")
    if wanted:
        for f in files:
            if os.path.basename(f) == wanted:
                return f
    cfg = load_json(os.path.join(CONFIG_DIR, "models.json"), {}) or {}
    default_id = cfg.get("default")
    for m in cfg.get("models", []):
        if m.get("id") == default_id:
            for f in files:
                if os.path.basename(f) == m.get("file"):
                    return f
    # Otherwise, use the largest available model (usually the best one the user downloaded).
    return max(files, key=os.path.getsize)


def find_zims():
    return sorted(glob.glob(os.path.join(ZIM_DIR, "**", "*.zim"), recursive=True))


def _ensure_exec(path):
    if not is_windows():
        try:
            os.chmod(path, os.stat(path).st_mode | 0o111)
        except OSError:
            pass


def _env_for(binary):
    env = os.environ.copy()
    bindir = os.path.dirname(binary)
    if sys.platform == "darwin":
        env["DYLD_LIBRARY_PATH"] = bindir + os.pathsep + env.get("DYLD_LIBRARY_PATH", "")
    elif not is_windows():
        env["LD_LIBRARY_PATH"] = bindir + os.pathsep + env.get("LD_LIBRARY_PATH", "")
    # Local services must not use a proxy.
    env["NO_PROXY"] = "127.0.0.1,localhost"
    return env


def _spawn(cmd, logname):
    os.makedirs(LOG_DIR, exist_ok=True)
    log = open(os.path.join(LOG_DIR, logname), "ab")
    kwargs = {"stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL, "env": _env_for(cmd[0])}
    if is_windows():
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(cmd, **kwargs)


class Launcher:
    def __init__(self, settings, say=print):
        self.settings = settings
        self.say = say
        self.procs = []

    def start_llm(self):
        port = int(self.settings.get("llm_port", 8091))
        if port_in_use(port):
            self.say(f"  • AI engine is already running on port {port}.")
            return True
        binary, kind = find_llama_server()
        model = find_model(self.settings)
        if not binary or not model:
            if not binary:
                self.say("  • AI engine (llama.cpp) not found in runtime/ — run 'python emergency.py prepare'.")
            if not model:
                self.say("  • No .gguf model in models/ — run 'python emergency.py prepare'.")
            self.say("    (If you use Ollama, it will be detected automatically.)")
            return False
        _ensure_exec(binary)
        from .generation import generation_options
        try:
            ctx = str(generation_options(self.settings, 'llamacpp', os.path.basename(model))['context'])
        except ValueError as e:
            self.say('  Invalid generation settings: ' + str(e))
            return False
        if kind == "llamafile":
            cmd = [binary, "--server", "--nobrowser", "-m", model, "--host", "127.0.0.1", "--port", str(port), "-c", ctx]
            if is_windows() and not binary.lower().endswith(".exe"):
                self.say("  • On Windows, llamafile must end in .exe — rename the file.")
                return False
        else:
            cmd = [binary, "-m", model, "--host", "127.0.0.1", "--port", str(port), "-c", ctx]
        threads = int(self.settings.get("llm_threads", 0) or 0)
        if threads > 0:
            cmd += ["-t", str(threads)]
        try:
            self.procs.append(_spawn(cmd, "llm.log"))
            self.say(f"  • Starting AI engine: {os.path.basename(model)} (loading may take up to 1 minute)")
            return True
        except OSError as e:
            self.say(f"  • Failed to start AI engine: {e} (see logs/llm.log)")
            return False

    def start_kiwix(self):
        if not self.settings.get("kiwix_enabled", True):
            return False
        port = int(self.settings.get("kiwix_port", 8092))
        if port_in_use(port):
            self.say(f"  • Kiwix is already running on port {port}.")
            return True
        zims = find_zims()
        if not zims:
            self.say("  • No .zim libraries in zim/ — the AI will use only the kit guides.")
            return False
        binary = find_kiwix_serve()
        if not binary:
            self.say("  • kiwix-serve not found. Run 'python emergency.py prepare' or enable 'Local Kiwix Server' in Kiwix Desktop")
            self.say(f"    and set kiwix_url in config/settings.local.json (current: {self.settings.get('kiwix_url')}).")
            return False
        _ensure_exec(binary)
        cmd = [binary, "--address", "127.0.0.1", "--port", str(port)] + zims
        try:
            self.procs.append(_spawn(cmd, "kiwix.log"))
            self.say(f"  • Starting Kiwix with {len(zims)} library/libraries.")
            return True
        except OSError as e:
            self.say(f"  • Failed to start kiwix-serve: {e} (see logs/kiwix.log)")
            return False

    def stop(self):
        for p in self.procs:
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass
        self.procs = []
