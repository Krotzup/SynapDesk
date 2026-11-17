"""CLI administrativa explícita: primer admin y auditoría en una transacción."""

import argparse
import getpass
from pathlib import Path
import sys
import warnings

from pydantic import SecretStr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.persistencia.entornos import seleccionar_configuracion_bd
from app.seguridad.bootstrap_admin import (
    CodigoBootstrap as C, ErrorBootstrap, ServicioBootstrapAdmin,
)


class ArgumentosSeguros(argparse.ArgumentParser):
    def error(self, message):
        # argparse normal repetiría argumentos desconocidos, incluidos secretos.
        raise ErrorBootstrap(C.ENTRADA)


def leer_datos():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise ErrorBootstrap(C.ENTRADA)
    correo = input("Correo del administrador: ")
    nombre = input("Nombre del administrador: ")
    with warnings.catch_warnings():
        # getpass no puede degradar a entrada visible si falla el terminal.
        warnings.simplefilter("error", getpass.GetPassWarning)
        try:
            clave = SecretStr(getpass.getpass("Contraseña: "))
            confirmacion = SecretStr(getpass.getpass("Confirma la contraseña: "))
        except getpass.GetPassWarning:
            raise ErrorBootstrap(C.ENTRADA) from None
    return dict(nombre=nombre, correo=correo, contrasena=clave, confirmacion=confirmacion)


def main(argumentos=None) -> int:
    servicio = None
    try:
        parser = ArgumentosSeguros(description=__doc__, allow_abbrev=False)
        parser.add_argument("--base", required=True, choices=("principal", "testing"))
        parser.add_argument("--ensayar", action="store_true",
                            help="Solo en base temporal localhost:5433; siempre rollback, sin alta.")
        args = parser.parse_args(argumentos)
        if args.ensayar and args.base != "testing":
            raise ErrorBootstrap(C.DESTINO)
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise ErrorBootstrap(C.ENTRADA)
        servicio = ServicioBootstrapAdmin(seleccionar_configuracion_bd(args.base))
        acreditado = None
        if args.ensayar:
            servicio._destino_ensayo(servicio.destino)
            print("Ensayo reversible. No se creará un administrador persistente.")
            esperado = servicio.destino
        else:
            acreditado = servicio.verificar_destino()
            esperado = acreditado.confirmacion
        print("Destino: " + esperado)
        accion = "el ensayo reversible" if args.ensayar else "la creación del administrador inicial"
        destino = input(f"Escribe el destino exacto para confirmar {accion}: ")
        if destino != esperado:
            raise ErrorBootstrap(C.DESTINO)
        preparado = servicio.preparar(**leer_datos())
        if args.ensayar:
            servicio.ensayar(preparado, confirmar_destino=destino)
            print("Ensayo validado y revertido. No se creó ninguna cuenta persistente.")
        else:
            servicio.crear(preparado, destino=acreditado, confirmar_destino=destino)
            print("Administrador inicial y auditoría confirmados.")
        return 0
    except ErrorBootstrap as error:
        print(str(error), file=sys.stderr)
        return 2
    except (KeyboardInterrupt, EOFError):
        print("Operación cancelada; no se confirma ninguna creación.", file=sys.stderr)
        return 2
    except Exception:
        # Mensaje fijo; no exception/input/DSN/SQL/traceback del driver o Settings.
        print("No se pudo completar la operación administrativa.", file=sys.stderr)
        return 2
    finally:
        if servicio is not None:
            try:
                servicio.cerrar()
            except Exception:
                print("No se pudo finalizar la operación administrativa.", file=sys.stderr)
                return 2


if __name__ == "__main__":
    sys.exit(main())
