"""Põe ?v=<hash do conteúdo> nas referências a css/ e js/ locais das páginas de docs/.

A zona gfvdata.com na Cloudflare força Browser Cache TTL de 4h nos assets (o HTML vem com
max-age=0). Sem versão na URL, o navegador roda o HTML novo com o JS velho. Chamado pelo
.githooks/pre-commit; imprime as páginas alteradas (uma por linha) para o hook dar `git add`.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
REF = re.compile(r'((?:href|src)=")((?:css|js)/[^"?#]+)(?:\?v=[0-9a-f]*)?(")')


def hash_asset(caminho: Path) -> str:
    # CRLF -> LF: o mesmo conteúdo dá o mesmo hash no Windows e no checkout do Pages.
    return hashlib.sha1(caminho.read_bytes().replace(b"\r\n", b"\n")).hexdigest()[:8]


def versionar(texto: str, docs: Path = DOCS) -> str:
    def trocar(m: re.Match) -> str:
        asset = docs / m.group(2)
        if not asset.is_file():
            return m.group(0)
        return f"{m.group(1)}{m.group(2)}?v={hash_asset(asset)}{m.group(3)}"
    return REF.sub(trocar, texto)


def main(docs: Path = DOCS) -> list[Path]:
    alteradas = []
    for pagina in sorted(docs.glob("*.html")):
        texto = pagina.read_text(encoding="utf-8")
        novo = versionar(texto, docs)
        if novo != texto:
            pagina.write_text(novo, encoding="utf-8", newline="")
            alteradas.append(pagina)
    return alteradas


if __name__ == "__main__":
    for p in main():
        print(p)
    sys.exit(0)
