from argon2 import PasswordHasher, Type, extract_parameters
from argon2.exceptions import HashingError, InvalidHashError, VerificationError, VerifyMismatchError

from app.configuracion import Configuracion


class ErrorContrasena(ValueError):
    """Error interno saneado, sin entrada ni hash en el mensaje."""


class ServicioContrasenas:
    """Argon2id con sal aleatoria; solo recibe hashes del almacenamiento confiable."""

    def __init__(self, configuracion: Configuracion) -> None:
        self._hasher = PasswordHasher(
            memory_cost=configuracion.auth_argon2_memoria_kib,
            time_cost=configuracion.auth_argon2_iteraciones,
            parallelism=configuracion.auth_argon2_paralelismo,
            hash_len=32,
            salt_len=16,
            type=Type.ID,
        )

    @staticmethod
    def _entrada_valida(contrasena: str) -> bool:
        if not isinstance(contrasena, str) or not contrasena:
            return False
        try:
            contrasena.encode("utf-8")
        except UnicodeEncodeError:
            return False
        return True

    @staticmethod
    def _hash_valido(hash_guardado: str) -> bool:
        if not isinstance(hash_guardado, str):
            return False
        try:
            parametros = extract_parameters(hash_guardado)
        except (InvalidHashError, ValueError):
            return False
        return (
            parametros.type == Type.ID
            and parametros.version == 19
            and 1 <= parametros.parallelism <= 2**24 - 1
            and 8 * parametros.parallelism <= parametros.memory_cost <= 2**32 - 1
            and 1 <= parametros.time_cost <= 2**32 - 1
            and parametros.salt_len >= 8
            and parametros.hash_len >= 4
        )

    def generar_hash(self, contrasena: str) -> str:
        if not self._entrada_valida(contrasena):
            raise ErrorContrasena("No se pudo proteger la contraseña.")
        try:
            return self._hasher.hash(contrasena)
        except HashingError:
            raise ErrorContrasena("No se pudo proteger la contraseña.") from None

    def verificar(self, hash_guardado: str, contrasena: str) -> bool:
        # El hash proviene del almacenamiento confiable: un registro inválido
        # es un fallo interno, no evidencia de una contraseña incorrecta.
        if not self._hash_valido(hash_guardado):
            raise ErrorContrasena("El hash de contraseña almacenado es inválido o incompatible.")
        if not self._entrada_valida(contrasena):
            return False
        try:
            return self._hasher.verify(hash_guardado, contrasena)
        except VerifyMismatchError:
            return False
        except InvalidHashError:
            raise ErrorContrasena("El hash de contraseña almacenado es inválido o incompatible.") from None
        except VerificationError:
            raise ErrorContrasena("No se pudo verificar la contraseña.") from None

    def necesita_rehash(self, hash_guardado: str) -> bool:
        """Consultar solo tras verificar; un hash inválido no se puede renovar."""
        if not self._hash_valido(hash_guardado):
            return False
        return self._hasher.check_needs_rehash(hash_guardado)
