"""Optional NVIDIA CUDA/Vulkan comparison using isolated downloaded runtimes."""
import argparse
import json
from pathlib import Path
import socket
import statistics
import sys
import time
import urllib.request
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app import launcher, prepare
from app.config import platform_key


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--download', action='store_true', help='download CPU, Vulkan, CUDA and CUDA libraries')
    parser.add_argument('--runtime-dir', default='runtime/acceleration-check', help='isolated test runtime/cache directory')
    parser.add_argument('--model', default='LFM3-1.7B-Q4_K_M.gguf', help='an already-installed model filename')
    args = parser.parse_args()
    root = str(Path(args.runtime_dir).resolve())
    probe = launcher.gpu_devices
    results = {}
    # Use only the NVIDIA device(s) for both backends; do not include an Intel iGPU.
    def nvidia_devices(binary, backend):
        return [(key, name) for key, name in probe(binary, backend) if 'NVIDIA' in name]
    with patch.object(prepare, 'RUNTIME_DIR', root), patch.object(launcher, 'RUNTIME_DIR', root), \
            patch.object(launcher, 'LOG_DIR', root), patch.object(launcher, 'gpu_devices', side_effect=nvidia_devices):
        if args.download:
            assert prepare.get_llama(platform_key(), prepare.T['en'], cuda=True), 'Download/install failed'
        for mode in ('cuda', 'vulkan'):
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                port = sock.getsockname()[1]
            engine = launcher.Launcher({'llm_acceleration': mode, 'llm_port': port,
                                       'llm_context': 4096, 'llm_max_tokens': 256})
            try:
                assert engine.start_llm(args.model), 'Engine did not start'
                assert engine.llm_acceleration == mode, 'Requested backend fell back: ' + str(engine.llm_acceleration)
                runs = []
                for _ in range(3):
                    request = urllib.request.Request(f'http://127.0.0.1:{port}/v1/chat/completions',
                        data=json.dumps({'messages': [{'role': 'user', 'content':
                            'Explain how a bicycle works in simple language. Write at least 200 words.'}],
                            'temperature': 0, 'seed': 42, 'max_tokens': 128,
                            'cache_prompt': False, 'chat_template_kwargs': {'enable_thinking': False}}).encode(),
                        headers={'Content-Type': 'application/json'})
                    start = time.monotonic()
                    with urllib.request.urlopen(request, timeout=120) as response:
                        answer = json.load(response)
                    elapsed = time.monotonic() - start
                    assert answer['choices'][0]['message'].get('content'), 'No visible response'
                    runs.append({'seconds': round(elapsed, 3), 'tokens': answer['usage']['completion_tokens'],
                                 'tokens_per_second': round(answer['usage']['completion_tokens'] / elapsed, 2),
                                 'timings': answer.get('timings')})
                results[mode] = {'model': args.model, 'runs': runs,
                                 'median_tokens_per_second': statistics.median(r['tokens_per_second'] for r in runs)}
                print(json.dumps({mode: results[mode]}, indent=2), flush=True)
            finally:
                engine.stop()
        Path(root, 'comparison.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
