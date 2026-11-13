"""Exercise the browser Markdown renderer with Node, without a DOM."""
import json
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which('node'), 'Node is required for renderer tests')
class MarkdownTests(unittest.TestCase):
    def render(self, text):
        script = r'''
const fs = require('fs'), vm = require('vm');
const source = fs.readFileSync('web/app.js', 'utf8');
const context = vm.createContext({});
vm.runInContext(source.slice(source.indexOf('// ---------------- markdown'),
                            source.indexOf('// ---------------- API')), context);
process.stdout.write(context.md(JSON.parse(fs.readFileSync(0, 'utf8')), {cites:true}));
'''
        result = subprocess.run(['node', '-e', script], input=json.dumps(text), cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_arrows_in_generated_prose(self):
        html = self.render(r'cloth $\rightarrow$ sand $\longrightarrow$ gravel [1]')
        self.assertIn('cloth → sand → gravel', html)
        self.assertIn('data-cite="1"', html)
        self.assertNotIn('$', html)

    def test_delimiters_and_common_arrow_commands(self):
        html = self.render(r'\(\leftarrow\) $$\Rightarrow$$ \[\leftrightarrow\] \downarrow')
        self.assertIn('← ⇒ ↔ ↓', html)

    def test_code_remains_literal(self):
        html = self.render('`$\\rightarrow$`\n\n```text\n$\\rightarrow$\n```')
        self.assertIn('<code>$\\rightarrow$</code>', html)
        self.assertIn('<pre><code>$\\rightarrow$\n</code></pre>', html)
        self.assertNotIn('→', html)

    def test_unknown_math_currency_and_html_stay_safe(self):
        html = self.render(r'$x^2$ costs $5. \rightarrowward <img src=x onerror=alert(1)> →')
        self.assertIn('$x^2$ costs $5.', html)
        self.assertIn(r'\rightarrowward', html)
        self.assertNotIn('<img', html)
        self.assertIn('&lt;img', html)
