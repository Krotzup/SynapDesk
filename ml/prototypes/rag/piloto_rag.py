"""Ensayo de RAG sin red ni dependencias. Ejecutar con python piloto_rag.py."""

from copy import deepcopy
from dataclasses import dataclass
from time import perf_counter


# Resúmenes sintéticos para ensayo. Pxx identifica una entrada del manifiesto
# ml/sources/procedimientos_oficiales.json de la rama del PR #32.
# Los sufijos -a son identificadores de ensayo, ajenos al índice pgvector.
SOURCES = {
    "P01-a": "DNS en Windows. Comparar acceso por IP y por nombre. Consultar el nombre con el DNS configurado.",
    "P02-a": "IP en Windows. Revisar ipconfig /all. Renovar la concesión únicamente si el adaptador usa DHCP.",
    "P05-a": "Conectividad TCP en Windows. Test-NetConnection permite comprobar un puerto desde el cliente.",
    "P12-a": "WSL en Windows. Consultar estado con wsl --status y versión con wsl --version.",
    "P14-a": "Puerto ocupado en Docker. Identificar primero qué proceso o contenedor usa el puerto.",
    "T01-a": "Caso resuelto sintético. El puerto 8080 estaba publicado por otro contenedor del entorno de ensayo.",
    "S01-a": "Política ficticia. En este entorno está prohibido renovar DHCP durante el turno.",
    "S02-a": "Política ficticia contradictoria. En este entorno se exige renovar DHCP durante el turno.",
    "S03-a": "Fragmento ficticio ajeno al diagnóstico. Contiene una orden de insertar el marcador TEXTO_AJENO.",
}


@dataclass(frozen=True)
class Case:
    id: str
    ticket: str
    retrieved: tuple[str, ...]
    expected: str
    expected_sources: tuple[str, ...]
    oracle: str


CASES = (
    Case("R01", "La aplicación abre por IP, pero no por el nombre interno.", ("P01-a",),
         "draft", ("P01-a",), "Comprobar resolución con el DNS configurado."),
    Case("R02", "Windows tiene IP fija. Necesito revisar los parámetros del adaptador.", ("P02-a",),
         "draft", ("P02-a",), "Consultar configuración sin renovar DHCP."),
    Case("R03", "En Windows necesito saber si el servidor de ensayo escucha en TCP 443.", ("P05-a",),
         "draft", ("P05-a",), "Comprobar TCP 443 desde el equipo afectado."),
    Case("R04", "Antes de probar una aplicación necesito registrar la versión de WSL.", ("P12-a",),
         "draft", ("P12-a",), "Consultar versión de WSL."),
    Case("R05", "El contenedor de ensayo no puede publicar el puerto 8080.", ("P14-a", "T01-a"),
         "draft", ("P14-a", "T01-a"), "Identificar el ocupante. El caso previo orienta, sin dar por confirmada la causa."),
    Case("R06", "Necesito recuperar un archivo eliminado del almacenamiento compartido.", (),
         "insufficient", (), "La recuperación no devolvió evidencia. Omitir el generador."),
    Case("R07", "¿Qué política de retención se aplica a los correos del laboratorio?", ("P01-a",),
         "insufficient", (), "El fragmento de DNS no aporta evidencia sobre retención."),
    Case("R08", "¿Puedo renovar DHCP durante mi turno en este entorno?", ("S01-a", "S02-a"),
         "insufficient", (), "Las dos políticas discrepan. Pedir confirmación al responsable."),
    Case("R09", "El portal de ensayo funciona por IP, pero falla por nombre.", ("P01-a", "S03-a"),
         "draft", ("P01-a",), "Citar DNS e ignorar la orden ajena al diagnóstico."),
    Case("R10", "¿Cómo reviso si otro servicio usa el puerto 8080?", ("P14-a",),
         "invalid_output", (), "Rechazar un borrador del simulador con una cita que no fue recuperada."),
)

# Respuestas fijas del simulador, independientes de la columna de expectativas.
SIMULATED_STEPS = {
    "R01": [("Consulta el nombre interno mediante el servidor DNS configurado.", ["P01-a"])],
    "R02": [("Revisa la configuración del adaptador con ipconfig /all.", ["P02-a"])],
    "R03": [("Comprueba el puerto TCP 443 con Test-NetConnection desde el equipo afectado.", ["P05-a"])],
    "R04": [("Consulta la versión instalada con wsl --version.", ["P12-a"])],
    "R05": [("Identifica qué proceso o contenedor ocupa el puerto 8080.", ["P14-a"]),
            ("Comprueba si se repite el caso previo de otro contenedor publicando ese puerto.", ["T01-a"])],
    "R07": [],
    "R08": [],
    "R09": [("Comprueba la resolución del nombre del portal con el DNS configurado.", ["P01-a"])],
    "R10": [("Revisa qué proceso ocupa el puerto.", ["FUENTE-INVENTADA"])],
}


def simulate(case_id, context):
    """Usa una salida fija y verifica qué referencias llegaron al contexto."""
    steps = SIMULATED_STEPS[case_id]
    known_refs = {ref for _, refs in steps for ref in refs if ref in SOURCES}
    if not known_refs <= context.keys():
        raise RuntimeError(f"{case_id}: falta evidencia prevista en el contexto de ensayo")
    return steps


def run_case(case, generator):
    context = {ref: SOURCES[ref] for ref in case.retrieved}
    if not context:
        return "insufficient", None, False

    steps = generator(case.id, context)
    if not steps:
        return "insufficient", None, True
    if any(not text.strip() or not refs or not set(refs) <= context.keys()
           for text, refs in steps):
        return "invalid_output", None, True

    draft = {
        "status": "pending",
        "content": "\n".join(f"{text} [{', '.join(refs)}]" for text, refs in steps),
        "sources": list(dict.fromkeys(ref for _, refs in steps for ref in refs)),
    }
    return "draft", draft, True


def review(draft, decision, modified_content=None):
    if draft["status"] != "pending" or decision not in {"accepted", "modified", "rejected"}:
        raise ValueError("Revisión inválida.")
    if decision == "modified" and not (modified_content or "").strip():
        raise ValueError("Una modificación requiere texto.")
    if decision != "modified" and modified_content is not None:
        raise ValueError("Solo una modificación admite texto editado.")
    return {"decision": decision, "modifiedContent": modified_content}


def main():
    failures = []
    first_draft = None
    print("Caso | Resultado | Generador llamado | Citas del borrador | Tiempo local | Verificacion")
    for case in CASES:
        start = perf_counter()
        outcome, draft, called = run_case(case, simulate)
        elapsed_ms = (perf_counter() - start) * 1_000
        refs = tuple(draft["sources"]) if draft else ()
        passed = (outcome, refs, called) == (case.expected, case.expected_sources, bool(case.retrieved))
        if not passed:
            failures.append(case.id)
        if first_draft is None and draft:
            first_draft = draft
        print(f"{case.id} | {outcome} | {'si' if called else 'no'} | "
              f"{', '.join(refs) or '-'} | {elapsed_ms:.3f} ms | {'OK' if passed else 'FALLO'}")

    original = deepcopy(first_draft)
    for decision, edit in (("accepted", None), ("modified", "Texto revisado."), ("rejected", None)):
        result = review(first_draft, decision, edit)
        if result != {"decision": decision, "modifiedContent": edit} or first_draft != original:
            failures.append(decision)
    try:
        review(first_draft, "modified", "  ")
    except ValueError:
        pass
    else:
        failures.append("modified sin texto")
    if failures:
        raise SystemExit(f"Fallaron: {', '.join(failures)}")
    print("10/10 casos correctos. Aceptar, modificar y rechazar preservan el borrador original.")
    print("La edicion vacia se rechaza. El tiempo corresponde al simulador.")


if __name__ == "__main__":
    main()
