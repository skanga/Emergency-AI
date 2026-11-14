"""Start the local engines (llama.cpp and kiwix-serve) available in the kit."""

import glob
import os
import re
import shutil
import socket
import subprocess
import sys
import time

from .config import LOG_DIR, MODELS_DIR, RUNTIME_DIR, ZIM_DIR, exe, is_windows, load_json, platform_key, CONFIG_DIR
from .net import get_json


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


def find_llama_server(backend=None):
    plat = platform_key()
    if backend in ("vulkan", "cuda"):
        found = _find_in(os.path.join(RUNTIME_DIR, "llama.cpp", plat + "-" + backend), [exe("llama-server")])
        return (found, "llama.cpp") if found else (None, None)
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
    with open(os.path.join(LOG_DIR, logname), "ab") as log:
        kwargs = {"stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL, "env": _env_for(cmd[0])}
        if is_windows():
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        return subprocess.Popen(cmd, **kwargs)


def gpu_devices(binary, backend):
    """Probe the engine on this machine, including its driver dependencies."""
    _ensure_exec(binary)
    try:
        result = subprocess.run([binary, "--list-devices"], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=15,
                                env=_env_for(binary), stdin=subprocess.DEVNULL,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if is_windows() else 0)
        if result.returncode:
            return []
        prefix = {"vulkan": r"Vulkan\d+", "cuda": r"CUDA\d+", "metal": r"MTL\d+|Metal\d*"}[backend]
        pattern = rf"^\s*({prefix}):\s*(.+)$"
        return re.findall(pattern, result.stdout + "\n" + result.stderr, re.MULTILINE)
    except (OSError, subprocess.TimeoutExpired):
        return []


class Launcher:
    def __init__(self, settings, say=print):
        self.settings = settings
        self.say = say
        self.procs = []
        self.llm_process = None
        self.llm_model = None
        self.llm_acceleration = None

    def _gpu_ready(self, process, port):
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            if self.llm_process is not process or process.poll() is not None:
                return False
            try:
                if get_json(f"http://127.0.0.1:{port}/health", timeout=2).get("status") == "ok":
                    return True
            except (OSError, ValueError):
                pass
            time.sleep(0.5)
        return False

    def start_llm(self, model_file=None):
        port = int(self.settings.get("llm_port", 8091))
        if port_in_use(port):
            self.say(f"  • AI engine is already running on port {port}.")
            return True
        binary, kind = find_llama_server()
        acceleration = self.settings.get("llm_acceleration", "auto")
        if acceleration not in ("auto", "cpu", "cuda", "vulkan", "metal"):
            self.say("  Invalid llm_acceleration: use auto, cpu, cuda, vulkan, or metal.")
            return False
        model = os.path.join(MODELS_DIR, model_file) if model_file else find_model(self.settings)
        if model_file and not os.path.isfile(model):
            model = None
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
        # Probe at every launch: a portable kit may now be on a different machine.
        if kind != "llamafile":
            backends = (["metal"] if platform_key().startswith("macos-") else ["cuda", "vulkan"])
            if acceleration != "auto":
                backends = [] if acceleration == "cpu" else ["cuda", "vulkan"] if acceleration == "cuda" else [acceleration]
            for backend in backends:
                gpu = binary if backend == "metal" and platform_key().startswith("macos-") else None
                if backend in ("vulkan", "cuda"):
                    gpu, _ = find_llama_server(backend)
                devices = gpu_devices(gpu, backend) if gpu else []
                if devices:
                    gpu_cmd = [gpu] + cmd[1:] + ["--device", ",".join(d[0] for d in devices),
                                               "--n-gpu-layers", "auto", "--fit", "on"]
                    self.say(f"  Starting AI with {backend}: " + "; ".join(d[1] for d in devices))
                    try:
                        process = _spawn(gpu_cmd, "llm.log")
                    except OSError as e:
                        self.say(f"  GPU startup failed: {e}")
                    else:
                        self.llm_process = process
                        self.llm_model = os.path.basename(model)
                        self.llm_acceleration = backend
                        self.procs.append(process)
                        try:
                            ready = self._gpu_ready(process, port)
                        except BaseException:
                            # Startup precedes the web server's normal cleanup block.
                            self.stop_llm()
                            raise
                        if ready:
                            self.say(f"  AI ready using {backend}.")
                            return True
                        # A concurrent stop cancels loading and must not restart it.
                        if self.llm_process is not process:
                            return False
                        try:
                            self.stop_llm()
                        except (OSError, subprocess.TimeoutExpired) as e:
                            self.say(f"  Could not stop GPU engine; fallback cancelled: {e}")
                            return False
                    self.say(f"  {backend} failed to load the model; trying the next backend. See logs/llm.log.")
                else:
                    self.say(f"  No usable {backend} device/build; trying the next backend.")
            cmd += ["--device", "none", "--n-gpu-layers", "0"]
        elif acceleration == "cpu":
            cmd += ["-ngl", "0"]
        try:
            self.llm_process = _spawn(cmd, "llm.log")
            self.llm_model = os.path.basename(model)
            self.llm_acceleration = "cpu" if kind != "llamafile" or acceleration == "cpu" else "llamafile"
            self.procs.append(self.llm_process)
            self.say(f"  • Starting AI engine ({self.llm_acceleration}): {os.path.basename(model)} (loading may take up to 1 minute)")
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

    @staticmethod
    def _stop_process(process):
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, TimeoutError):
            process.kill()
            # Confirm exit before another model can allocate memory.
            process.wait(timeout=5)

    def stop_llm(self):
        if self.llm_process is not None:
            process = self.llm_process
            self.llm_process = None  # Cancel an in-progress GPU readiness wait.
            self._stop_process(process)
            self.procs.remove(process)
        self.llm_model = None
        self.llm_acceleration = None

    def stop(self):
        self.llm_process = None
        for process in list(self.procs):
            try:
                self._stop_process(process)
            except (OSError, subprocess.TimeoutExpired):
                pass
        self.procs = []
        self.llm_process = None
        self.llm_model = None
        self.llm_acceleration = None
