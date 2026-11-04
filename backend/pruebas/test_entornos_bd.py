import pytest

from app.persistencia.entornos import seleccionar_configuracion_bd


def test_testing_utiliza_sus_credenciales_y_no_las_principales(monkeypatch) -> None:
    variables = {
        "POSTGRES_HOST": "host_principal",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "base_principal",
        "POSTGRES_USER": "usuario_principal",
        "POSTGRES_PASSWORD": "clave_ficticia_principal",
        "POSTGRES_TEST_HOST": "host_testing",
        "POSTGRES_TEST_PORT": "5433",
        "POSTGRES_TEST_DB": "base_testing",
        "POSTGRES_TEST_USER": "usuario_testing",
        "POSTGRES_TEST_PASSWORD": "clave_ficticia_testing",
    }
    for nombre, valor in variables.items():
        monkeypatch.setenv(nombre, valor)

    configuracion = seleccionar_configuracion_bd("testing")

    assert configuracion.app_env == "testing"
    assert configuracion.postgres_host == "host_testing"
    assert configuracion.postgres_port == 5433
    assert configuracion.postgres_db == "base_testing"
    assert configuracion.postgres_user == "usuario_testing"
    assert configuracion.postgres_password.get_secret_value() == "clave_ficticia_testing"


def test_seleccion_desconocida_no_utiliza_la_base_principal() -> None:
    with pytest.raises(ValueError, match="base=principal o base=testing"):
        seleccionar_configuracion_bd("testng")
