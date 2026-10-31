"""The built page loads nothing from the network: fonts, icons, images and styles are self-hosted (UI v3)."""
import re
from pathlib import Path

import pytest

DIST = Path(__file__).resolve().parents[1] / "frontend/dist"
EXTERNAL_HTML = re.compile(r"""(?:src|href)\s*=\s*["'](?:https?:)?//""", re.I)
EXTERNAL_CSS = re.compile(r"""url\(\s*["']?(?:https?:)?//|@import\s+(?:url\()?["']?(?:https?:)?//""", re.I)


@pytest.mark.skipif(not (DIST / "index.html").exists(), reason="frontend not built")
def test_built_page_has_no_external_resources():
    hits = [f"index.html: {m.group(0)}" for m in EXTERNAL_HTML.finditer((DIST / "index.html").read_text(encoding="utf-8"))]
    for css in (DIST / "assets").glob("*.css"):
        hits += [f"{css.name}: {m.group(0)}" for m in EXTERNAL_CSS.finditer(css.read_text(encoding="utf-8"))]
    assert not hits, "external resources in the built page:\n" + "\n".join(hits)
    assert list((DIST / "assets").glob("*dm-serif-display*.woff2")), "display font is not bundled"
