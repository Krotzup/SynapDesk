"""Reconstruye el piloto por huellas; nunca ejecuta comandos de sus documentos."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from .html_procedures import BeautifulSoup, render, select_section

MAX_SOURCE_BYTES = 5_000_000
ALLOWED_HOSTS = {"learn.microsoft.com", "docs.docker.com", "raw.githubusercontent.com"}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.port not in (None, 443)
            or parsed.username is not None or parsed.password is not None):
        raise ValueError("La fuente debe pertenecer a un host HTTPS oficial permitido.")


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(request, file, code, message, headers, newurl)


def read_source(url, expected, cached=None):
    validate_url(url)
    if cached is not None:
        with cached.open("rb") as stream:
            raw = stream.read(MAX_SOURCE_BYTES + 1)
    else:
        opener = build_opener(OfficialRedirects())
        with opener.open(Request(url, headers={"User-Agent": "SynapDesk-source-verification/1.0"}), timeout=30) as response:
            raw = response.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES or digest(raw) != expected:
        raise ValueError("La fuente cambió o supera el límite; conservar la versión anterior y revisar una nueva versión del registro.")
    return raw


def extract_document(spec, raw, *, retrieval=False):
    soup = BeautifulSoup(raw, "html.parser")
    candidates = soup.select("main .content") if "learn.microsoft.com" in spec["url"] else soup.select("main article")
    title = soup.select_one("main h1")
    if not candidates or title is None:
        raise ValueError("No se encontró el artículo oficial esperado.")
    source = max(candidates, key=lambda node: len(node.get_text()))
    sections = spec.get("section")
    sections = sections if isinstance(sections, list) else [sections]
    selected = BeautifulSoup("<div></div>", "html.parser").div
    for identifier in sections:
        part = select_section(source, identifier)
        for child in list(part.children):
            selected.append(BeautifulSoup(str(child), "html.parser"))
    body = re.sub(r"\n{3,}", "\n\n", render(selected)).strip()
    url = spec["url"] + ("#" + sections[0] if sections[0] else "")
    text = (spec["title"] + "\nAplicabilidad editorial: " + spec["applies"] + "\n\n"
            + title.get_text(" ", strip=True) + "\n\n" + body + "\n\n"
            + "Procedencia: " + spec["publisher"] + "\nFuente publicada: " + url
            + "\nLicencia del repositorio fuente: " + spec["licenseId"] + "; véanse catálogo y avisos adjuntos.\n")
    encoded = text.encode("utf-8")
    if len(encoded) > 1_000_000 or digest(encoded) != spec["expectedTextSha256"]:
        raise ValueError("El texto extraído no coincide con el piloto; no se sustituye silenciosamente.")
    if retrieval:
        # Los encabezados de atribución añadidos por el proyecto quedan en el
        # archivo de archivo/catálogo, no como falsos fragmentos recuperables.
        return (title.get_text(" ", strip=True) + "\n\n" + body + "\n").encode("utf-8")
    return encoded


def build(registry_path, output, cache_dir=None):
    if output.exists():
        raise ValueError("La carpeta de salida debe ser nueva; no se sobrescriben corpus existentes.")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    originals, documents = {}, []
    for spec in registry["sources"]:
        name = Path(spec["sourceSnapshot"]).name
        if not re.fullmatch(r"source_\d+\.html", name):
            raise ValueError("Nombre de snapshot no válido.")
        if name not in originals:
            cached = cache_dir / "sources" / name if cache_dir else None
            originals[name] = read_source(spec["url"], spec["sourceSha256"], cached)
        documents.append((spec, extract_document(spec, originals[name]),
                          extract_document(spec, originals[name], retrieval=True)))
    licenses = []
    for item in registry["licenses"]:
        name = Path(item["file"]).name
        cached = cache_dir / "licenses" / name if cache_dir else None
        licenses.append((name, read_source(item["url"], item["sha256"], cached)))
    output.mkdir(parents=True)
    for folder in ("documents", "retrieval", "sources", "licenses"):
        (output / folder).mkdir()
    for name, raw in originals.items():
        (output / "sources" / name).write_bytes(raw)
    for name, raw in licenses:
        (output / "licenses" / name).write_bytes(raw)
    catalog, cases = [], []
    for spec, raw, body in documents:
        name = spec["id"].lower() + ".txt"
        (output / "documents" / name).write_bytes(raw)
        (output / "retrieval" / name).write_bytes(body)
        catalog.append(dict(spec, file="documents/" + name, sha256=digest(raw),
                            retrievalFile="retrieval/" + name, retrievalSha256=digest(body),
                            preprocessingVersion="official_body_v1",
                            sourceUrl=spec["url"] + ("#" + (spec["section"][0] if isinstance(spec["section"], list) else spec["section"]) if spec["section"] else "")))
        for index, query in enumerate(spec["queries"], 1):
            cases.append({"queryId": spec["id"] + "-" + str(index), "query": query,
                          "answerable": True, "expectedDocumentId": spec["documentId"]})
    for index, query in enumerate(("¿Cómo recupero un archivo eliminado de SharePoint?",
                                  "Necesito configurar SMTP en Thunderbird para enviar correo.",
                                  "¿Cómo recupero una base de datos Oracle a un punto anterior en el tiempo?"), 1):
        cases.append({"queryId": "NEG-" + str(index), "query": query, "answerable": False})
    (output / "catalog.json").write_text(json.dumps({"corpusId": registry["corpusId"], "documents": catalog,
        "distributionStatus": registry["distributionStatus"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "cases.json").write_text(json.dumps({"annotationStatus": "synthetic_pending_human_review", "queries": cases}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    files = sorted(path for path in output.rglob("*") if path.is_file())
    manifest = {"createdAt": datetime.now(timezone.utc).isoformat(), "registrySha256": digest(registry_path.read_bytes()),
                "sha256": {path.relative_to(output).as_posix(): digest(path.read_bytes()) for path in files}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"documents": len(documents), "sources": len(originals), "cases": len(cases)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=Path("ml/sources/procedimientos_oficiales.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, help="Corpus anterior con snapshots y licencias; solo se lee")
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.registry, args.output, args.cache_dir), ensure_ascii=False))
    except (ValueError, OSError) as error:
        parser.error(str(error))
