"""Switch one app-owned model at a time, between answer streams."""
import glob
import os
import re
import threading
import time
import urllib.parse

from .config import CONFIG_DIR, MODELS_DIR, load_json, save_local_settings
from .launcher import find_llama_server, port_in_use
from .net import get_json


class ModelManager:
    def __init__(self, engine, launcher, enabled=True):
        self.engine = engine
        self.launcher = launcher
        self.settings = engine.settings
        self.enabled = enabled
        self.condition = threading.Condition()
        self.answering = False
        self.closed = False
        self.phase = 'idle'
        self.target = None
        self.active = launcher.llm_model
        self.error = None
        self.started = None
        self.worker = None

    def _models(self):
        catalogue = load_json(os.path.join(CONFIG_DIR, 'models.json'), {}) or {}
        names = {m['file']: m['name'] for m in catalogue.get('models', [])}
        root = os.path.realpath(MODELS_DIR)
        models = []
        for path in sorted(glob.glob(os.path.join(MODELS_DIR, '*.gguf'))):
            filename = os.path.basename(path)
            shard = re.search(r'-(\d{5})-of-\d{5}\.gguf$', filename)
            if shard and shard[1] != '00001':
                continue
            # Never accept a path outside the installed-model directory, including symlinks.
            if os.path.dirname(os.path.realpath(path)) != root or not os.path.isfile(path):
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            if size:
                models.append({'file': filename, 'name': names.get(filename, filename), 'size_bytes': size})
        return models

    def _disabled_reason(self):
        if not self.enabled or self.closed:
            return 'disabled'
        if self.settings.get('llm_backend', 'auto') not in ('auto', 'llamacpp', 'openai'):
            return 'external'
        try:
            url = urllib.parse.urlsplit(self.settings.get('llm_url', 'http://127.0.0.1:8091/v1'))
            port = int(self.settings.get('llm_port', 8091))
            local = url.scheme == 'http' and url.hostname in ('127.0.0.1', 'localhost') and url.port == port
        except ValueError:
            local = False
        if not local:
            return 'external'
        if self.launcher.llm_process is None and port_in_use(port):
            return 'external'
        if not find_llama_server()[0]:
            return 'missing_engine'
        return None

    def _status(self):
        process = self.launcher.llm_process
        if self.active and self.phase in ('idle', 'ready') and process is not None and process.poll() is not None:
            self.active, self.phase = None, 'error'
            self.error = 'AI engine exited. Retry or select another model. See logs/llm.log.'
        reason = self._disabled_reason()
        return {'enabled': reason is None, 'reason': reason, 'models': self._models(),
                'active': self.active, 'selected': self.settings.get('model_file'),
                'target': self.target, 'phase': self.phase, 'error': self.error,
                'elapsed': round(time.monotonic() - self.started, 1) if self.started else 0}

    def status(self):
        with self.condition:
            return self._status()

    def begin_answer(self):
        with self.condition:
            if self.closed or self.answering or self.phase in ('queued', 'stopping', 'loading'):
                return False
            self.answering = True
            return True

    def end_answer(self):
        with self.condition:
            self.answering = False
            self.condition.notify_all()

    def request(self, filename):
        with self.condition:
            if not isinstance(filename, str) or filename not in {m['file'] for m in self._models()}:
                raise ValueError('Choose an installed GGUF model filename.')
            if self._disabled_reason():
                raise RuntimeError('Only a local AI engine managed by this app can switch models.')
            if self.phase in ('queued', 'stopping', 'loading'):
                raise RuntimeError('A model switch is already in progress.')
            self.phase = 'queued' if self.answering else 'stopping'
            self.target, self.error = filename, None
            self.started = time.monotonic()
            state = self._status()
            self.worker = threading.Thread(target=self._switch, args=(filename,), daemon=True)
            self.worker.start()
            return state

    def _phase(self, phase):
        with self.condition:
            self.phase = phase

    def _wait_ready(self):
        deadline = time.monotonic() + 300
        port = int(self.settings.get('llm_port', 8091))
        while time.monotonic() < deadline:
            with self.condition:
                if self.closed:
                    raise RuntimeError('App is shutting down.')
            process = self.launcher.llm_process
            if process is None or process.poll() is not None:
                raise RuntimeError('AI engine exited while loading. See logs/llm.log.')
            try:
                if get_json('http://127.0.0.1:%d/health' % port, timeout=2).get('status') == 'ok':
                    return
            except (OSError, ValueError):
                pass
            with self.condition:
                self.condition.wait(0.5)
        raise RuntimeError('Model did not load within 5 minutes. See logs/llm.log.')

    def _switch(self, filename):
        previous = self.settings.get('model_file')
        try:
            with self.condition:
                while self.answering and not self.closed:
                    self.condition.wait()
                if self.closed:
                    return
                self.phase = 'stopping'
            self.launcher.stop_llm()
            with self.condition:
                self.active = None
            # Recheck installation after waiting for an answer to finish.
            if filename not in {m['file'] for m in self._models()}:
                raise RuntimeError('Selected model is no longer installed.')
            self.settings['model_file'] = filename
            self.engine.reset_llm()
            self._phase('loading')
            if not self.launcher.start_llm(filename):
                raise RuntimeError('Unable to start the selected model. See logs/llm.log.')
            self._wait_ready()
            save_local_settings({'model_file': filename})
            self.engine.reset_llm()
            with self.condition:
                self.active, self.phase = filename, 'ready'
        except Exception as error:
            try:
                self.launcher.stop_llm()
            except Exception:
                pass
            if previous is None:
                self.settings.pop('model_file', None)
            else:
                self.settings['model_file'] = previous
            self.engine.reset_llm()
            with self.condition:
                self.phase, self.error = 'error', str(error)

    def close(self):
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        if self.worker:
            self.worker.join(10)
