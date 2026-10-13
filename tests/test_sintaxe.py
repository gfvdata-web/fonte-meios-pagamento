"""Sintaxe: Python compila, JSON/CSV parseiam e todo JS (arquivos e <script> inline) passa no `node --check`."""
from __future__ import annotations

import csv
import json
import py_compile
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests.helpers import DOCS, RAIZ
from tests.test_paginas import PAGINAS, Pagina

NODE = shutil.which("node")


def _arquivos(base: str, padrao: str) -> list[Path]:
    return sorted((RAIZ / base).rglob(padrao))


class TestSintaxe(unittest.TestCase):
    def test_python_compila(self):
        alvos = [RAIZ / "run_pipeline.py", *_arquivos("src", "*.py"), *_arquivos("tests", "*.py"),
                 *_arquivos(".github/scripts", "*.py"), *_arquivos("skill", "*.py")]
        self.assertGreater(len(alvos), 10)
        with tempfile.TemporaryDirectory() as tmp:
            for i, arq in enumerate(alvos):
                try:
                    py_compile.compile(str(arq), cfile=str(Path(tmp) / f"{i}.pyc"), doraise=True)
                except py_compile.PyCompileError as exc:
                    self.fail(f"{arq.relative_to(RAIZ)}: {exc.msg}")

    def test_json_valido(self):
        alvos = _arquivos("docs/dados", "*.json") + _arquivos("tests/fixtures", "*.json")
        self.assertGreaterEqual(len(alvos), 5)
        for arq in alvos:
            try:
                json.loads(arq.read_text(encoding="utf-8"))
            except ValueError as exc:
                self.fail(f"JSON inválido {arq.relative_to(RAIZ)}: {exc}")

    def test_csv_com_colunas_consistentes(self):
        for arq in (DOCS / "dados" / "meios_pagamento_mensal.csv", RAIZ / "dados" / "processados" / "meios_pagamento_mensal.csv"):
            with arq.open(encoding="utf-8", newline="") as f:
                linhas = list(csv.reader(f))
            self.assertTrue(all(len(l) == len(linhas[0]) for l in linhas), arq.name)

    @unittest.skipIf(NODE is None, "node não instalado")
    def test_js_dos_arquivos(self):
        alvos = _arquivos("docs/js", "*.js") + _arquivos("tests/js", "*.js")
        self.assertGreaterEqual(len(alvos), 3)
        for arq in alvos:
            r = subprocess.run([NODE, "--check", str(arq)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, f"{arq.relative_to(RAIZ)}:\n{r.stderr.strip()}")

    @unittest.skipIf(NODE is None, "node não instalado")
    def test_js_inline_das_paginas(self):
        with tempfile.TemporaryDirectory() as tmp:
            for nome in PAGINAS:
                pagina = Pagina((DOCS / nome).read_text(encoding="utf-8"))
                for i, codigo in enumerate(pagina.scripts_inline):
                    if not codigo.strip():
                        continue
                    tmp_js = Path(tmp) / f"{nome}.{i}.js"
                    tmp_js.write_text(codigo, encoding="utf-8")
                    r = subprocess.run([NODE, "--check", str(tmp_js)], capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, f"<script> #{i} de docs/{nome}:\n{r.stderr.strip()}")


if __name__ == "__main__":
    unittest.main()
