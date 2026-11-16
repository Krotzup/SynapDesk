"""Regresiones de las guardas de CI; no duplican pruebas de autenticación."""

from copy import deepcopy
from types import SimpleNamespace

import pytest
from yaml.constructor import ConstructorError

from herramientas import ci_backend
from herramientas.validar_ci import (
    RAIZ, WORKFLOW, PLANTILLA_URL, anclas, cargar_workflow, hallazgos, markdown,
    secretos, validar_enlace, workflow,
)


@pytest.mark.parametrize("entorno,host,puerto", [
    ("production", "127.0.0.1", 5433), ("testing", "externo.invalid", 5433),
    ("testing", "127.0.0.1", 5432), ("testing", "localhost", 5432),
    ("testing", "127.0.0.1", 0), ("development", "localhost", 5433),
])
def test_destinos_ajenos_rechazados_antes_de_conectar(entorno, host, puerto):
    with pytest.raises(ValueError):
        ci_backend.comprobar_destino(SimpleNamespace(app_env=entorno, postgres_host=host, postgres_port=puerto))


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "::1"])
def test_destino_local_explicito_permitido(host):
    ci_backend.comprobar_destino(SimpleNamespace(app_env="testing", postgres_host=host, postgres_port=5433))


@pytest.mark.parametrize("marca", ["failure", "error", "skipped", "vacio"])
def test_ci_no_confunde_fallos_omisiones_o_cero_tests_con_exito(tmp_path, marca):
    xml = "<testsuite/>" if marca == "vacio" else f"<testsuite><testcase><{marca}/></testcase></testsuite>"
    ruta = tmp_path / "junit.xml"
    ruta.write_text(xml)
    with pytest.raises(ValueError):
        ci_backend.comprobar_resultados(ruta)


def test_junit_correcto_y_codigo_de_proceso_fallido(tmp_path, monkeypatch):
    ruta = tmp_path / "junit.xml"
    ruta.write_text("<testsuite><testcase/><testcase/></testsuite>")
    assert ci_backend.comprobar_resultados(ruta) == 2
    monkeypatch.setattr(ci_backend.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError):
        ci_backend.ejecutar_pytest([], tmp_path)


def test_suite_desconocida_no_abre_infraestructura(monkeypatch):
    monkeypatch.setattr(ci_backend, "comprobar_importaciones", lambda: pytest.fail("No debe preparar infraestructura"))
    with pytest.raises(ValueError):
        ci_backend.ejecutar("ajena")


@pytest.fixture
def configuracion_workflow():
    return cargar_workflow((RAIZ / WORKFLOW).read_text(encoding="utf-8"))


def test_workflow_activa_cinco_cambios_exclusivos(configuracion_workflow):
    resultado = workflow(configuracion_workflow)
    assert len(resultado["activacion_exclusiva"]) == 5
    assert all(resultado["activacion_exclusiva"].values())
    assert resultado["eventos"] == ["pull_request/main", "push/main"]


@pytest.mark.parametrize("cambio", ["paths", "permisos", "job_if", "paso_omitible", "quitar_suite",
                                   "servicio_externo", "puerto_principal", "accion_mutable", "checkout_credenciales"])
def test_workflow_rechaza_omisiones_y_configuracion_peligrosa(configuracion_workflow, cambio):
    datos = deepcopy(configuracion_workflow)
    job = datos["jobs"]["postgresql"]
    if cambio == "paths":
        datos["on"]["pull_request"]["paths"] = ["ml/**"]
    elif cambio == "permisos":
        datos["permissions"] = {"contents": "write"}
    elif cambio == "job_if":
        job["if"] = "false"
    elif cambio == "paso_omitible":
        job["steps"][-1]["continue-on-error"] = True
    elif cambio == "quitar_suite":
        job["steps"][-1]["run"] = "echo omitida"
    elif cambio == "servicio_externo":
        job["env"]["POSTGRES_TEST_HOST"] = "externo.invalid"
    elif cambio == "puerto_principal":
        job["services"]["postgres"]["ports"] = ["5432:5432"]
    elif cambio == "accion_mutable":
        job["steps"][1]["uses"] = "actions/checkout@main"
    else:
        job["steps"][1]["with"]["persist-credentials"] = True
    with pytest.raises(ValueError):
        workflow(datos)


def test_yaml_duplicado_e_inseguro_no_se_acepta():
    with pytest.raises(ValueError):
        cargar_workflow("jobs: {}\njobs: {}\n")
    with pytest.raises(ConstructorError):
        cargar_workflow("!!python/object/apply:os.system ['echo indebido']")


def test_anclas_unicode_repetidas_setext_y_codigo():
    texto = "# Sesión válida\n# Sesión válida\nTítulo\n------\n```md\n# Ignorar\n```\n<a id=\"explicita\"></a>"
    assert anclas(texto) == {"sesión-válida", "sesión-válida-1", "título", "explicita"}
    visible, bloques = markdown('```json\n{"ok":true}\n```\n[enlace](real.md)')
    assert bloques == ['{"ok":true}'] and "[enlace]" in visible
    with pytest.raises(ValueError):
        markdown("```json\nsin cierre")


def test_archivo_privado_local_no_es_destino_versionado():
    with pytest.raises(ValueError):
        validar_enlace("docs/contratos/autenticacion-v1.md", "../../.env", set())


def test_ancla_inexistente_se_rechaza():
    with pytest.raises(ValueError):
        validar_enlace("CONTRIBUTING.md", "#ancla-que-no-existe", {"CONTRIBUTING.md"})
    validar_enlace("CONTRIBUTING.md", "#idioma", {"CONTRIBUTING.md"})


@pytest.mark.parametrize("regla,valor", [
    ("clave_privada", ("-" * 5 + "BEGIN PRIVATE KEY" + "-" * 5).encode()),
    ("token_github", ("ghp_" + "A" * 36).encode()),
    ("clave_aws", ("AKIA" + "A" * 16).encode()),
    ("url_postgresql", ("postgresql" + "://usuario:" + "clave_real@host/base").encode()),
    ("variable_secreta", ("AUTH_TOKEN" + "=credencial_operativa").encode()),
])
def test_scanner_rechaza_patrones_sin_exponer_su_valor(regla, valor):
    resultado = hallazgos("backend/ejemplo.py", valor)
    assert any(h["rule"] == regla for h in resultado)
    assert valor.decode() not in repr(resultado)


def test_plantilla_publica_no_es_exencion_para_otros_archivos():
    assert hallazgos(".env.example", PLANTILLA_URL) == []
    assert hallazgos("backend/credenciales.py", PLANTILLA_URL)


def test_scanner_completo_falla_sin_imprimir_el_token(tmp_path, monkeypatch, capsys):
    from herramientas import validar_ci
    monkeypatch.setattr(validar_ci, "RAIZ", tmp_path)
    (tmp_path / "backend").mkdir()
    valor = "ghp_" + "B" * 36
    (tmp_path / "backend/ejemplo.py").write_text(valor)
    with pytest.raises(ValueError):
        secretos({"backend/ejemplo.py"})
    salida = capsys.readouterr().out
    assert "token_github" in salida and valor not in salida


def test_cli_fallido_devuelve_uno_sin_exponer_excepciones(monkeypatch, capsys):
    def fallar(_):
        raise RuntimeError("contenido privado de ensayo")
    monkeypatch.setattr(ci_backend, "ejecutar", fallar)
    monkeypatch.setattr(ci_backend.sys, "argv", ["ci_backend", "unitarias"])
    assert ci_backend.main() == 1
    assert "contenido privado" not in capsys.readouterr().err
