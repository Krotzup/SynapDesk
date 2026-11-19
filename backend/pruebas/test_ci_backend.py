"""Regresiones de las guardas de CI; no duplican pruebas de autenticación."""

from copy import deepcopy
from contextlib import contextmanager
import os
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


@pytest.mark.parametrize("evento", ["opened", "synchronize", "reopened", "edited", "ready_for_review"])
def test_workflow_cubre_cambio_de_base_y_salida_de_draft(configuracion_workflow, evento):
    pr = configuracion_workflow["on"]["pull_request"]
    assert pr["branches"] == ["main"]
    assert evento in pr.get("types", ["opened", "synchronize", "reopened"])


def test_workflow_activa_cinco_cambios_exclusivos(configuracion_workflow):
    resultado = workflow(configuracion_workflow)
    assert len(resultado["activacion_exclusiva"]) == 5
    assert all(resultado["activacion_exclusiva"].values())
    assert resultado["eventos"] == ["pull_request/main", "push/main"]
    assert resultado["tipos_pull_request"] == [
        "opened", "synchronize", "reopened", "edited", "ready_for_review",
    ]


@pytest.mark.parametrize("evento", ["opened", "synchronize", "reopened", "edited", "ready_for_review"])
def test_workflow_rechaza_perder_cualquiera_de_los_eventos(configuracion_workflow, evento):
    datos = deepcopy(configuracion_workflow)
    datos["on"]["pull_request"]["types"].remove(evento)
    with pytest.raises(ValueError):
        workflow(datos)


def test_workflow_rechaza_volver_a_eventos_implicitos(configuracion_workflow):
    datos = deepcopy(configuracion_workflow)
    del datos["on"]["pull_request"]["types"]
    with pytest.raises(ValueError):
        workflow(datos)


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


def test_scanner_exime_solo_la_asignacion_dinamica_historica():
    ruta = "backend/herramientas/ingreso_local/demo.py"
    dinamica = b"POSTGRES_TEST_PASSWORD=principal.postgres_password.get_secret_value())"
    assert hallazgos(ruta, dinamica) == []
    assert hallazgos("backend/otro.py", dinamica)
    assert hallazgos(ruta, b"POSTGRES_TEST_PASSWORD=clave_literal_de_ensayo")


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


def crear_enlace_de_ensayo(enlace, destino):
    try:
        enlace.symlink_to(destino, target_is_directory=True)
    except OSError as error:
        if os.name != "nt" or error.winerror != 1314:
            raise
        # Windows sin privilegio de symlinks: la misma guarda rechaza junctions.
        from _winapi import CreateJunction
        CreateJunction(str(destino), str(enlace))


@pytest.fixture
def infraestructura_ci_aislada(tmp_path, monkeypatch):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from app.persistencia import entornos
    from herramientas.arnes_http_seguro import infraestructura

    scripts = ScriptDirectory.from_config(Config(str(ci_backend.BACKEND / "alembic.ini")))
    backend = tmp_path / "backend"
    backend.mkdir()
    observado = {}
    monkeypatch.setattr(ci_backend, "BACKEND", backend)
    monkeypatch.setattr(infraestructura, "BACKEND", backend)
    monkeypatch.setattr(ScriptDirectory, "from_config", lambda _: scripts)
    monkeypatch.setattr(entornos, "seleccionar_configuracion_bd", lambda _: SimpleNamespace(
        app_env="testing", postgres_host="127.0.0.1", postgres_port=5433))

    @contextmanager
    def base_simulada(carpeta, evidencia):
        observado["recursos"] = carpeta
        try:
            yield None, "synapdesk_base_simulada"
        finally:
            observado["base_cerrada"] = True

    # Solo sustituye PostgreSQL; directorios y guarda de borrado son reales.
    monkeypatch.setattr(infraestructura, "base_propia", base_simulada)
    return observado


def test_postgresql_pytest_real_con_current_limpia_sin_relajar_guarda(
    infraestructura_ci_aislada, tmp_path, monkeypatch,
):
    script = tmp_path / "test_temporal_aislado.py"
    script.write_text(
        "import os\n"
        "def test_temporal(tmp_path):\n"
        "    (tmp_path / 'inesperado.tmp').write_text('ensayo')\n"
        "    if os.name == 'nt':\n"
        "        from _winapi import CreateJunction\n"
        "        CreateJunction(str(tmp_path), str(tmp_path.parent / 'ensayocurrent'))\n",
        encoding="utf-8",
    )
    ejecutar_real = ci_backend.ejecutar_pytest
    observado = infraestructura_ci_aislada

    def ejecutar_ensayo(argumentos, temporal, env):
        observado["pytest"] = temporal
        assert argumentos == [
            "pruebas/integracion",
            "--ignore=" + ci_backend.TLS,
            "--ignore=" + ci_backend.BUSQUEDA,
        ]
        assert env["EJECUTAR_PRUEBAS_BD"] == "1"
        assert env["POSTGRES_TEST_DB"] == "synapdesk_base_simulada"
        return ejecutar_real([str(script)], temporal, env)

    monkeypatch.setattr(ci_backend, "ejecutar_pytest", ejecutar_ensayo)
    resultado = ci_backend.ejecutar("postgresql")
    assert resultado["passed"] == 1 and resultado["skipped"] == 0
    assert resultado["temporary_deleted"] and resultado["pytest_temporary_deleted"]
    assert observado["base_cerrada"]
    assert not observado["pytest"].exists() and not observado["recursos"].exists()
    assert not observado["pytest"].is_relative_to(observado["recursos"])
    assert not observado["recursos"].is_relative_to(observado["pytest"])


def test_postgresql_limpia_archivos_propios_inesperados_sin_tocar_ajenos(
    infraestructura_ci_aislada, tmp_path, monkeypatch,
):
    observado = infraestructura_ci_aislada
    destino_ajeno = tmp_path / "ajeno"
    destino_ajeno.mkdir()
    ajeno = destino_ajeno / "inesperado.tmp"
    ajeno.write_text("conservar")

    def ejecutar_ensayo(_, temporal, env):
        observado["pytest"] = temporal
        (temporal / "subdirectorio").mkdir()
        (temporal / "subdirectorio/inesperado.tmp").write_text("propio")
        crear_enlace_de_ensayo(temporal / "inesperadocurrent", destino_ajeno)
        return 1

    monkeypatch.setattr(ci_backend, "ejecutar_pytest", ejecutar_ensayo)
    assert ci_backend.ejecutar("postgresql")["temporary_deleted"]
    assert not observado["pytest"].exists() and not observado["recursos"].exists()
    assert ajeno.read_text() == "conservar"


@pytest.mark.parametrize("nombre", ["ensayocurrent", "enlace_inesperado"])
@pytest.mark.parametrize("externo", [False, True])
def test_postgresql_rechaza_enlaces_en_recursos_aunque_se_llamen_current(
    infraestructura_ci_aislada, tmp_path, monkeypatch, nombre, externo,
):
    observado = infraestructura_ci_aislada
    ajeno = tmp_path / "ajeno"
    ajeno.mkdir()
    marcador = ajeno / "conservar.txt"
    marcador.write_text("conservar")

    def ejecutar_ensayo(_, temporal, env):
        observado["pytest"] = temporal
        recursos = observado["recursos"]
        destino = ajeno if externo else recursos / "interno"
        if not externo:
            destino.mkdir()
        crear_enlace_de_ensayo(recursos / nombre, destino)
        return 1

    monkeypatch.setattr(ci_backend, "ejecutar_pytest", ejecutar_ensayo)
    with pytest.raises(AssertionError):
        ci_backend.ejecutar("postgresql")
    assert observado["recursos"].exists()  # Rechazo antes de borrar recursos.
    assert not observado["pytest"].exists()
    assert marcador.read_text() == "conservar"


@pytest.mark.parametrize("fallo", ["excepcion", "residuo"])
def test_postgresql_limpieza_pytest_fallida_no_se_presenta_como_exito(
    infraestructura_ci_aislada, tmp_path, monkeypatch, capsys, fallo,
):
    observado = infraestructura_ci_aislada
    temporal = tmp_path / "pytest_no_eliminado"

    @contextmanager
    def temporal_fallido(**kwargs):
        temporal.mkdir()
        yield str(temporal)
        if fallo == "excepcion":
            raise PermissionError("detalle privado de limpieza")

    monkeypatch.setattr(ci_backend, "TemporaryDirectory", temporal_fallido)
    monkeypatch.setattr(ci_backend, "ejecutar_pytest", lambda *args: 1)
    monkeypatch.setattr(ci_backend.sys, "argv", ["ci_backend", "postgresql"])
    assert ci_backend.main() == 1
    salida = capsys.readouterr()
    error = "PermissionError" if fallo == "excepcion" else "RuntimeError"
    assert "CI_BACKEND_FAILED: " + error in salida.err
    assert "detalle privado" not in salida.err and not salida.out
    assert observado["base_cerrada"] and not observado["recursos"].exists()
    assert temporal.exists()


def test_postgresql_error_de_borrado_de_recursos_tambien_falla_el_job(
    infraestructura_ci_aislada, monkeypatch, capsys,
):
    from herramientas.arnes_http_seguro import infraestructura
    observado = infraestructura_ci_aislada

    def ejecutar_ensayo(_, temporal, env):
        observado["pytest"] = temporal
        return 1

    def borrar_fallido(carpeta):
        raise PermissionError("detalle privado de recursos")

    monkeypatch.setattr(ci_backend, "ejecutar_pytest", ejecutar_ensayo)
    monkeypatch.setattr(infraestructura, "borrar_temporal", borrar_fallido)
    monkeypatch.setattr(ci_backend.sys, "argv", ["ci_backend", "postgresql"])
    assert ci_backend.main() == 1
    salida = capsys.readouterr()
    assert "CI_BACKEND_FAILED: PermissionError" in salida.err
    assert "detalle privado" not in salida.err and not salida.out
    assert observado["base_cerrada"] and observado["recursos"].exists()
    assert not observado["pytest"].exists()
