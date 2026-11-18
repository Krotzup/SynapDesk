"""Guardas que impiden dirigir el arnés a recursos ajenos o heredar TLS inseguro."""

from types import SimpleNamespace

import pytest

from herramientas.arnes_http_seguro.ejecutar import entorno_node, ejecutar
from herramientas.arnes_http_seguro.infraestructura import borrar_temporal, comprobar_base


@pytest.mark.parametrize("host,puerto,nombre", [
    ("remoto.invalid", 5433, "synapdesk_auth07_sec01a_" + "a" * 32),
    ("localhost", 5432, "synapdesk_auth07_sec01a_" + "a" * 32),
    ("localhost", 5433, "desarrollo"),
    ("localhost", 5433, "synapdesk_auth07_sec01a_../ajena"),
    ("localhost", 5433, "synapdesk_auth07_sec01a_" + "G" * 32),
])
def test_base_ajena_rechazada_antes_de_conectar(host, puerto, nombre):
    config = SimpleNamespace(postgres_host=host, postgres_port=puerto, postgres_db="control")
    with pytest.raises(ValueError):
        comprobar_base(config, nombre)


def test_base_control_no_es_objetivo_destructivo():
    nombre = "synapdesk_auth07_sec01a_" + "a" * 32
    config = SimpleNamespace(postgres_host="127.0.0.1", postgres_port=5433, postgres_db=nombre)
    with pytest.raises(ValueError):
        comprobar_base(config, nombre)


@pytest.mark.parametrize("nombre", ["../../privado.json", "auth07d2-arnes.json/otro", "evidencia.json"])
def test_reporte_no_puede_elegir_destino_arbitrario(nombre):
    with pytest.raises(ValueError):
        ejecutar(nombre)


def test_limpieza_no_admite_directorio_ajeno(tmp_path):
    marca = tmp_path / "preservar.txt"
    marca.write_text("preservar", encoding="utf-8")
    with pytest.raises(AssertionError):
        borrar_temporal(tmp_path)
    assert marca.read_text(encoding="utf-8") == "preservar"


def test_opciones_tls_inseguras_no_se_heredan(monkeypatch):
    monkeypatch.setenv("NODE_TLS_REJECT_UNAUTHORIZED", "0")
    monkeypatch.setenv("NODE_OPTIONS", "--require=ajeno")
    monkeypatch.setenv("NODE_EXTRA_CA_CERTS", "ca-ajena")
    env = entorno_node()
    assert not ({"NODE_TLS_REJECT_UNAUTHORIZED", "NODE_OPTIONS", "NODE_EXTRA_CA_CERTS"} & env.keys())
