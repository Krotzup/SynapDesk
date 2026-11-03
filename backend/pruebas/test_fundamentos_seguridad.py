import base64
import hashlib
import hmac

import pytest
from argon2 import Type, extract_parameters
from argon2.exceptions import HashingError
from pydantic import SecretStr, ValidationError

from app.configuracion import Configuracion
from app.persistencia.modelos import Usuario
from app.seguridad.contrasenas import ErrorContrasena, ServicioContrasenas
from app.seguridad.cuentas import normalizar_cuenta
from app.seguridad.identificadores import ServicioIdentificadores

# Solo datos públicos ficticios de testing; nunca una clave operativa.
CLAVE_FICTICIA = bytes(range(32))


def configuracion_prueba(**cambios) -> Configuracion:
    valores = {
        "app_env": "testing",
        "auth_argon2_memoria_kib": 1024,
        "auth_argon2_iteraciones": 1,
        "auth_argon2_paralelismo": 1,
        "auth_hmac_clave": SecretStr(base64.b64encode(CLAVE_FICTICIA).decode("ascii")),
        "auth_hmac_id_clave": "prueba-1",
    }
    valores.update(cambios)
    return Configuracion(_env_file=None, **valores)


@pytest.fixture
def contrasenas():
    return ServicioContrasenas(configuracion_prueba())


@pytest.fixture
def identificadores():
    return ServicioIdentificadores(configuracion_prueba())


def test_argon2id_hash_verificacion_sal_y_no_filtracion(contrasenas, caplog):
    secreto = "contraseña ficticia ñ 🔒"
    primero = contrasenas.generar_hash(secreto)
    segundo = contrasenas.generar_hash(secreto)
    assert primero != segundo
    assert secreto not in primero
    parametros = extract_parameters(primero)
    assert parametros.type == Type.ID
    assert (parametros.memory_cost, parametros.time_cost, parametros.parallelism) == (1024, 1, 1)
    assert parametros.salt_len == 16
    assert parametros.hash_len == 32
    assert contrasenas.verificar(primero, secreto)
    assert not contrasenas.verificar(primero, "otra contraseña")
    assert not contrasenas.necesita_rehash(primero)
    assert not caplog.records
    assert secreto not in repr(contrasenas)
    assert primero not in repr(contrasenas)


def test_contrasena_no_se_normaliza_ni_recorta(contrasenas):
    hash_guardado = contrasenas.generar_hash(" ClaveConEspacios ")
    assert contrasenas.verificar(hash_guardado, " ClaveConEspacios ")
    assert not contrasenas.verificar(hash_guardado, "ClaveConEspacios")
    assert not contrasenas.verificar(hash_guardado, " claveconespacios ")


@pytest.mark.parametrize("entrada", [None, 123, b"clave", "", "\ud800"])
def test_contrasena_invalida_no_filtra_entrada(contrasenas, entrada, caplog):
    with pytest.raises(ErrorContrasena, match="No se pudo proteger la contraseña") as error:
        contrasenas.generar_hash(entrada)
    assert not contrasenas.verificar("hash inválido", entrada)
    assert str(error.value) == "No se pudo proteger la contraseña."
    assert not caplog.records


@pytest.mark.parametrize("hash_invalido", [
    None, 123, "", "secreto-corrupto", "$argon2id$", "$argon2id$v=19$m=x,t=1,p=1$x$x",
    "$argon2id$v=19$m=1024,t=1,p=1$%%%$%%%",
    "$argon2id$v=19$m=18446744073709551616,t=1,p=1$YWJjZGVmZ2g$YWJjZGVmZ2g",
    "$argon2id$v=19$m=1024,t=0,p=1$YWJjZGVmZ2g$YWJjZGVmZ2g",
    "$argon2i$v=19$m=1024,t=1,p=1$YWJjZA$YWJjZA",
])
def test_hash_invalido_o_corrupto_no_autentica(contrasenas, hash_invalido, caplog):
    assert not contrasenas.verificar(hash_invalido, "clave ficticia")
    assert not caplog.records


def test_hash_alterado_no_autentica(contrasenas):
    hash_guardado = contrasenas.generar_hash("clave ficticia")
    partes = hash_guardado.split("$")
    partes[-1] = ("A" if partes[-1][0] != "A" else "B") + partes[-1][1:]
    assert not contrasenas.verificar("$".join(partes), "clave ficticia")


def test_rehash_no_modifica_hash_y_respeta_parametros_configurables(contrasenas):
    hash_guardado = contrasenas.generar_hash("ficticia")
    actualizado = ServicioContrasenas(configuracion_prueba(
        auth_argon2_memoria_kib=2048, auth_argon2_iteraciones=2, auth_argon2_paralelismo=2,
    ))
    assert actualizado.verificar(hash_guardado, "ficticia")
    assert actualizado.necesita_rehash(hash_guardado)
    nuevo = actualizado.generar_hash("ficticia")
    assert not actualizado.necesita_rehash(nuevo)
    assert not actualizado.necesita_rehash("hash inválido")
    parametros = extract_parameters(nuevo)
    assert (parametros.memory_cost, parametros.time_cost, parametros.parallelism) == (2048, 2, 2)


def test_parametros_provisionales_por_defecto_funcionan():
    configuracion = Configuracion(_env_file=None, app_env="testing")
    servicio = ServicioContrasenas(configuracion)
    hash_guardado = servicio.generar_hash("ficticia de prueba sin benchmark")
    parametros = extract_parameters(hash_guardado)
    assert (parametros.memory_cost, parametros.time_cost, parametros.parallelism) == (65536, 3, 1)
    assert servicio.verificar(hash_guardado, "ficticia de prueba sin benchmark")


def test_fallo_de_biblioteca_no_expone_mensaje(contrasenas, monkeypatch, caplog):
    def fallar(*args, **kwargs):
        raise HashingError("contraseña y hash sensibles")

    monkeypatch.setattr(type(contrasenas._hasher), "hash", fallar)
    with pytest.raises(ErrorContrasena) as error:
        contrasenas.generar_hash("secreto")
    assert str(error.value) == "No se pudo proteger la contraseña."
    assert error.value.__suppress_context__
    assert not caplog.records


@pytest.mark.parametrize("campo,valor", [
    ("auth_argon2_memoria_kib", 0), ("auth_argon2_memoria_kib", 2**32),
    ("auth_argon2_iteraciones", 0), ("auth_argon2_iteraciones", "inválido"),
    ("auth_argon2_paralelismo", 0), ("auth_argon2_paralelismo", 2**24),
    ("auth_argon2_paralelismo", 1024),
    ("auth_argon2_iteraciones", True),
])
def test_configuracion_rechaza_parametros_argon2_invalidos(campo, valor):
    with pytest.raises(ValidationError):
        configuracion_prueba(**{campo: valor})


def test_configuracion_usa_variables_existentes_y_oculta_clave(monkeypatch):
    texto = base64.b64encode(CLAVE_FICTICIA).decode("ascii")
    monkeypatch.setenv("AUTH_HMAC_CLAVE", texto)
    monkeypatch.setenv("AUTH_HMAC_ID_CLAVE", "prueba-env")
    monkeypatch.setenv("AUTH_ARGON2_MEMORIA_KIB", "2048")
    configuracion = Configuracion(_env_file=None, app_env="testing")
    assert configuracion.obtener_clave_hmac() == CLAVE_FICTICIA
    assert configuracion.auth_hmac_id_clave == "prueba-env"
    assert configuracion.auth_argon2_memoria_kib == 2048
    assert texto not in repr(configuracion)
    assert texto not in configuracion.model_dump_json()


@pytest.mark.parametrize("entorno", ["development", "testing", "staging", "production"])
def test_hmac_sin_secreto_falla_al_construir_servicio_en_cualquier_entorno(entorno):
    configuracion = Configuracion(_env_file=None, app_env=entorno)
    with pytest.raises(ValueError, match="Falta configurar la clave HMAC"):
        ServicioIdentificadores(configuracion)


@pytest.mark.parametrize("clave", [
    "", "no-es-base64", "secreto-ficticio",
    base64.b64encode(b"x" * 32).decode(),
    base64.b64encode(bytes(32)).decode(),
    base64.b64encode(bytes(range(31))).decode(),
    base64.b64encode(CLAVE_FICTICIA).decode() + "\n",
])
def test_hmac_rechaza_claves_invalidas_sin_filtrarlas(clave, caplog):
    with pytest.raises(ValidationError) as error:
        configuracion_prueba(auth_hmac_clave=clave)
    if clave:
        assert clave not in str(error.value)
    assert "input_value=" not in str(error.value)
    assert not caplog.records


@pytest.mark.parametrize("cambios", [
    {"auth_hmac_id_clave": None}, {"auth_hmac_clave": None},
    {"auth_hmac_id_clave": ""}, {"auth_hmac_id_clave": "espacios no"},
])
def test_clave_y_identificador_requieren_configuracion_coherente(cambios):
    with pytest.raises(ValidationError):
        configuracion_prueba(**cambios)


@pytest.mark.parametrize("entrada,esperado", [
    ("  AGENTE@Ejemplo.CL  ", "agente@ejemplo.cl"),
    ("\tAgente+Soporte@Ejemplo.CL\n", "agente+soporte@ejemplo.cl"),
    (" A.B@Ejemplo.CL ", "a.b@ejemplo.cl"),
    ("Ñ@EJEMPLO.CL", "ñ@ejemplo.cl"),
])
def test_normalizacion_compartida_con_usuario(entrada, esperado, identificadores):
    assert normalizar_cuenta(entrada) == esperado
    assert Usuario(correo=entrada).correo == esperado
    assert identificadores.cuenta(entrada) == identificadores.cuenta(esperado)


@pytest.mark.parametrize("entrada", [None, 123, False, b"correo", "", " \t\n", "a\x00b", "\ud800"])
def test_normalizacion_rechaza_entradas_no_persistibles(entrada, identificadores, caplog):
    with pytest.raises(ValueError, match="La cuenta debe ser texto"):
        normalizar_cuenta(entrada)
    with pytest.raises(ValueError, match="La cuenta debe ser texto"):
        identificadores.cuenta(entrada)
    assert not caplog.records


def test_normalizacion_no_inventa_equivalencias_de_proveedor(identificadores):
    assert identificadores.cuenta("a.b@ejemplo.cl") != identificadores.cuenta("ab@ejemplo.cl")
    assert identificadores.cuenta("a+b@ejemplo.cl") != identificadores.cuenta("a@ejemplo.cl")
    # El formato completo del correo corresponde al futuro contrato de entrada.
    assert normalizar_cuenta(" TextoNoVacio ") == "textonovacio"


def test_hmac_vector_dominio_longitud_clave_y_entrada(identificadores, caplog):
    digest = identificadores.cuenta(" AGENTE@EJEMPLO.CL ")
    esperado = hmac.digest(CLAVE_FICTICIA, b"synapdesk:auth:v1\x00cuenta\x00agente@ejemplo.cl", hashlib.sha256)
    assert digest == esperado
    assert len(digest) == 32
    assert digest == identificadores.cuenta("agente@ejemplo.cl")
    assert digest != identificadores.cuenta("otro@ejemplo.cl")
    distinto = ServicioIdentificadores(configuracion_prueba(
        auth_hmac_clave=SecretStr(base64.b64encode(bytes(range(1, 33))).decode()),
        auth_hmac_id_clave="prueba-2",
    ))
    assert digest != distinto.cuenta("agente@ejemplo.cl")
    # Mismo texto en dominios distintos nunca comparte identificador.
    assert identificadores.cuenta("192.0.2.1") != identificadores.ip_verificada("192.0.2.1")
    assert len(identificadores.ip_verificada("192.0.2.1")) == 32
    assert identificadores.id_clave == "prueba-1"
    assert not caplog.records
    assert "agente@ejemplo.cl" not in repr(identificadores)
    assert repr(CLAVE_FICTICIA) not in repr(identificadores)


@pytest.mark.parametrize("uno,dos", [
    ("2001:0db8:0000:0000:0000:0000:0000:0001", "2001:db8::1"),
    ("2001:DB8::A", "2001:db8::a"),
    ("::ffff:192.0.2.1", "192.0.2.1"),
])
def test_ip_canonica(identificadores, uno, dos):
    assert identificadores.ip_verificada(uno) == identificadores.ip_verificada(dos)
    assert identificadores.ip_verificada(uno) != identificadores.ip_verificada("192.0.2.2")


@pytest.mark.parametrize("entrada", [
    None, 123, "", " X-Forwarded-For: 192.0.2.1", "192.0.2.1, 192.0.2.2",
    "192.0.2.1:80", "192.0.2.1/24", "192.000.2.1", "fe80::1%eth0", " 192.0.2.1 ",
])
def test_ip_invalida_sin_filtracion(identificadores, entrada, caplog):
    with pytest.raises(ValueError) as error:
        identificadores.ip_verificada(entrada)
    assert str(error.value) == "La IP verificada no tiene una representación válida."
    assert not caplog.records
