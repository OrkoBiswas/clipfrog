"""Build identical, self-hosted caption faces for browsers and libass.

Requires fonttools and brotli only when regenerating assets. Run with
--refresh-sources to update the pinned Google Fonts sources, then commit the
source lock, generated catalog, licenses, TTFs and WOFF2s together.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tarfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets/fonts"
PUBLIC = ROOT / "apps/web/public/fonts"
LOCK = ASSETS / "caption-sources.json"
ALL_WEIGHTS = list(range(100, 901, 100))
FAMILIES = [
    ("Urbanist", ALL_WEIGHTS, True, "Sans serif"),
    ("Inter", ALL_WEIGHTS, True, "Sans serif"),
    ("Montserrat", ALL_WEIGHTS, True, "Sans serif"),
    ("Roboto", ALL_WEIGHTS, True, "Sans serif"),
    ("Lato", [100, 300, 400, 700, 900], True, "Sans serif"),
    ("Open Sans", list(range(300, 801, 100)), True, "Sans serif"),
    ("Noto Sans", ALL_WEIGHTS, True, "Sans serif"),
    ("DejaVu Sans", [400, 700], True, "Sans serif"),
    ("Bebas Neue", [400], False, "Display"),
    ("Poppins", ALL_WEIGHTS, True, "Sans serif"),
    ("Oswald", list(range(200, 701, 100)), False, "Condensed"),
    ("Roboto Condensed", ALL_WEIGHTS, True, "Condensed"),
    ("Raleway", ALL_WEIGHTS, True, "Sans serif"),
    ("Nunito Sans", list(range(200, 901, 100)), True, "Sans serif"),
    ("DM Sans", ALL_WEIGHTS, True, "Sans serif"),
    ("Playfair Display", list(range(400, 901, 100)), True, "Serif"),
]


def download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Clipfrog-Font-Bundler/1.0"})
    with urlopen(request, timeout=90) as response:
        return response.read()


def slug(family: str) -> str:
    return family.lower().replace(" ", "-")


def refresh_sources() -> list[dict]:
    revision = json.loads(download("https://api.github.com/repos/google/fonts/commits/main"))["sha"]

    def source(spec: tuple) -> dict:
        family, weights, italic, category = spec
        entry = {"family": family, "category": category, "variants": []}
        if family == "DejaVu Sans":
            archive_url = "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2"
            archive = download(archive_url)
            with tarfile.open(fileobj=BytesIO(archive), mode="r:bz2") as bundle:
                entry["license"] = bundle.extractfile("dejavu-fonts-ttf-2.37/LICENSE").read().decode()
            entry["license_url"] = archive_url
            for weight, style, filename in [
                (400, False, "DejaVuSans.ttf"),
                (700, False, "DejaVuSans-Bold.ttf"),
                (400, True, "DejaVuSans-Oblique.ttf"),
                (700, True, "DejaVuSans-BoldOblique.ttf"),
            ]:
                entry["variants"].append({"weight": weight, "italic": style, "url": archive_url, "member": "dejavu-fonts-ttf-2.37/ttf/" + filename})
            return entry
        tuples = ";".join(f"{i},{w}" for i in range(2 if italic else 1) for w in weights)
        css_url = "https://fonts.googleapis.com/css2?family=" + family.replace(" ", "+") + ":ital,wght@" + tuples
        css = download(css_url).decode()
        for face in re.findall(r"@font-face\s*\{([^}]+)\}", css):
            entry["variants"].append({
                "weight": int(re.search(r"font-weight:\s*(\d+)", face)[1]),
                "italic": "font-style: italic" in face,
                "url": re.search(r"url\(([^)]+)\)", face)[1],
            })
        assert len(entry["variants"]) == len(weights) * (2 if italic else 1), family
        entry["license_url"] = f"https://raw.githubusercontent.com/google/fonts/{revision}/ofl/{family.lower().replace(' ', '')}/OFL.txt"
        entry["license"] = download(entry["license_url"]).decode()
        entry["css_url"] = css_url
        return entry

    with ThreadPoolExecutor(max_workers=6) as pool:
        entries = list(pool.map(source, FAMILIES))
    LOCK.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return entries


def build(entries: list[dict]) -> None:
    # Cache sources so DejaVu's archive is fetched once, including on regeneration.
    cache = ROOT / ".local/caption-font-sources"
    cache.mkdir(parents=True, exist_ok=True)

    def fetch(url: str) -> None:
        target = cache / hashlib.sha256(url.encode()).hexdigest()
        if not target.exists():
            target.write_bytes(download(url))

    urls = {variant["url"] for entry in entries for variant in entry["variants"]}
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(fetch, sorted(urls)))

    def face(task: tuple) -> dict:
        index, entry, variant = task
        weight, italic = variant["weight"], variant["italic"]
        data = (cache / hashlib.sha256(variant["url"].encode()).hexdigest()).read_bytes()
        if "member" in variant:
            with tarfile.open(fileobj=BytesIO(data), mode="r:bz2") as archive:
                data = archive.extractfile(variant["member"]).read()
        digest = hashlib.sha256(data).hexdigest()
        if variant.get("sha256") and variant["sha256"] != digest:
            raise ValueError(f"Source checksum changed: {entry['family']} {weight}")
        variant["sha256"] = digest
        font = TTFont(BytesIO(data), recalcTimestamp=False)
        assert "fvar" not in font, "Only static faces may be exported"
        # The legacy-compatible Google TTF endpoint floors Thin/Extra Light at
        # 250 in OS/2 despite distinct outlines. Restore the requested CSS weight.
        font["OS/2"].usWeightClass = weight
        # Unique native families make libass select the actual face at every weight.
        # Names deliberately omit upstream Reserved Font Names after modification.
        native_family = f"Clipfrog CF{index + 1:02d} W{weight}" + (" Italic" if italic else "")
        postscript = native_family.replace(" ", "-")
        names = {1: native_family, 2: "Regular", 3: postscript, 4: native_family, 6: postscript, 16: native_family, 17: "Regular"}
        for name_id, name in names.items():
            font["name"].removeNames(nameID=name_id)
            font["name"].setName(name, name_id, 3, 1, 0x409)
            font["name"].setName(name, name_id, 1, 0, 0)
        relative = Path("caption") / slug(entry["family"]) / f"{weight}{'-italic' if italic else ''}.ttf"
        target = ASSETS / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        font.flavor = None
        font.save(target)
        web_file = relative.with_suffix(".woff2")
        web_target = PUBLIC / web_file
        web_target.parent.mkdir(parents=True, exist_ok=True)
        font.flavor = "woff2"
        font.save(web_target)
        return {"weight": weight, "italic": italic, "file": relative.as_posix(), "family": native_family, "web_file": web_file.as_posix()}

    tasks = [(i, entry, variant) for i, entry in enumerate(entries) for variant in entry["variants"]]
    with ThreadPoolExecutor(max_workers=6) as pool:
        faces = list(pool.map(face, tasks))
    catalog, css = [], ["/* Generated by scripts/build_caption_fonts.py. Self-hosted; loaded on demand. */"]
    cursor = 0
    for entry in entries:
        variants = faces[cursor:cursor + len(entry["variants"])]
        cursor += len(variants)
        variants.sort(key=lambda v: (v["weight"], v["italic"]))
        catalog.append({"family": entry["family"], "category": entry["category"], "weights": sorted({v["weight"] for v in variants}), "italic": any(v["italic"] for v in variants), "variants": variants})
        license_name = "LICENSE.txt" if entry["family"] == "DejaVu Sans" else "OFL.txt"
        for base in [ASSETS, PUBLIC]:
            target = base / "caption" / slug(entry["family"])
            (target / license_name).write_text(entry["license"], encoding="utf-8")
            (target / "SOURCE.txt").write_text(f"Original family: {entry['family']}\nLicense: {entry['license_url']}\nSource lock: assets/fonts/caption-sources.json\nModified: renamed to unique Clipfrog families for exact export face selection.\n", encoding="utf-8")
        for variant in variants:
            css.append("@font-face {\n" + f'  font-family: "{entry["family"]}";\n  font-style: {"italic" if variant["italic"] else "normal"};\n  font-weight: {variant["weight"]};\n  font-display: swap;\n  src: url("/fonts/{variant["web_file"]}") format("woff2");\n' + "}")
    output = ROOT / "packages/shared/caption-fonts.json"
    output.write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    shutil.copyfile(output, ROOT / "apps/api/clipforge_api/caption-fonts.json")
    (ROOT / "apps/web/src/app/caption-fonts.css").write_text("\n".join(css) + "\n", encoding="utf-8")
    LOCK.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    print(f"Bundled {len(catalog)} families / {len(faces)} real faces.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-sources", action="store_true")
    args = parser.parse_args()
    build(refresh_sources() if args.refresh_sources else json.loads(LOCK.read_text(encoding="utf-8")))
