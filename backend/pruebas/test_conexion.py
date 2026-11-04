from app.configuracion import Configuracion
from app.persistencia.conexion import construir_url_bd


def test_contrasena_con_caracteres_especiales_se_conserva_en_la_url() -> None:
    clave = "prueba@:/#% con espacios"
    configuracion = Configuracion(
        _env_file=None,
        postgres_host="127.0.0.1",
        postgres_port=5433,
        postgres_db="synapdesk_test",
        postgres_user="synapdesk_test",
        postgres_password=clave,
    )
    url = construir_url_bd(configuracion)

    assert url.drivername == "postgresql+psycopg"
    assert url.password == clave
    assert url.database == "synapdesk_test"
    assert clave not in str(url)
    assert clave not in repr(configuracion)


def test_contrasena_vacia_no_es_configuracion_bd_completa() -> None:
    configuracion = Configuracion(
        _env_file=None,
        postgres_db="synapdesk_test",
        postgres_user="synapdesk_test",
        postgres_password="",
    )
    assert not configuracion.tiene_configuracion_bd
