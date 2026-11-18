"""Evaluación con contexto preparado para un generador LLM del piloto."""

import argparse
import json
from time import perf_counter

from .piloto_rag import CASES, R09_FORBIDDEN_MARKER, SOURCES, Case, Generator, Step, generate_draft, make_simulator
from .prompt_rag import (
    BASELINE_PROMPT_VERSION,
    DEFAULT_PROMPT_VERSION,
    SYSTEM_PROMPTS,
    Complete,
    make_generator,
)


# R10 fuerza una salida inválida. Se comprueba con un doble de prueba.
EVALUATION_CASES = tuple(case for case in CASES if case.expected != "invalid_output")


def evaluate_sys_rag_001(
    complete: Complete, *, provider: str, model: str, cases: tuple[Case, ...] = EVALUATION_CASES
) -> dict:
    """Ejecuta la evaluación con SYS-RAG-001 y registra modelo y proveedor."""
    return evaluate_prompt(
        complete, provider=provider, model=model, prompt_version=BASELINE_PROMPT_VERSION, cases=cases
    )


def evaluate_prompt(
    complete: Complete,
    *,
    provider: str,
    model: str,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    cases: tuple[Case, ...] = EVALUATION_CASES,
) -> dict:
    """Ejecuta una versión del prompt con los casos elegidos."""
    report = evaluate_model(
        make_generator(complete, prompt_version=prompt_version),
        model=model, prompt_version=prompt_version, cases=cases,
    )
    report["provider"] = provider
    return report


def evaluate_model(
    generator: Generator, *, model: str, prompt_version: str, cases: tuple[Case, ...] = EVALUATION_CASES
) -> dict:
    """Devuelve un informe serializable con evidencia para revisión humana."""
    results = []
    for case in cases:
        fragments = {ref: SOURCES[ref] for ref in case.retrieved}
        start = perf_counter()
        outcome, draft, called = generate_draft(case.ticket, fragments, generator)
        latency_ms = round((perf_counter() - start) * 1000, 3) if called else None
        cited = draft["sources"] if draft else []
        steps = draft["steps"] if draft else ()
        result = {
            "caseId": case.id,
            "ticket": case.ticket,
            "fragments": fragments,
            "expectedOutcome": case.expected,
            "outcome": outcome,
            "outcomeMatches": outcome == case.expected,
            "expectedSources": list(case.expected_sources),
            "citedSources": cited,
            "sourceSetMatches": outcome == case.expected and set(cited) == set(case.expected_sources),
            "steps": serialize_steps(steps),
            "reviewCriterion": case.oracle,
            "generatorCalled": called,
            "latencyMs": latency_ms,
        }
        if case.id == "R09":
            marker = R09_FORBIDDEN_MARKER.casefold()
            result["forbiddenMarkerFound"] = any(marker in step.text.casefold() for step in steps)
        result["caseMatches"] = result["sourceSetMatches"] and not result.get("forbiddenMarkerFound", False)
        results.append(result)

    return {
        "model": model,
        "promptVersion": prompt_version,
        "summary": {
            "totalCases": len(results),
            "outcomeMatches": sum(result["outcomeMatches"] for result in results),
            "sourceSetMatches": sum(result["sourceSetMatches"] for result in results),
            "caseMatches": sum(result["caseMatches"] for result in results),
            "invalidOutputs": sum(result["outcome"] == "invalid_output" for result in results),
            "generatorCalls": sum(result["generatorCalled"] for result in results),
        },
        "cases": results,
    }


def serialize_steps(steps: tuple[Step, ...]) -> list[dict]:
    return [{"text": step.text, "fragmentIds": list(step.fragment_ids)} for step in steps]


def evaluate_simulated(*, prompt_version: str = DEFAULT_PROMPT_VERSION) -> dict:
    simulate = make_simulator()

    def complete(messages: list[dict[str, str]]) -> str:
        payload = json.loads(messages[1]["content"])
        steps = simulate(payload["ticket"], payload["fragments"])
        return json.dumps({"steps": serialize_steps(steps)})

    report = evaluate_prompt(
        complete,
        provider="Simulador local",
        model="Respuestas fijas",
        prompt_version=prompt_version,
    )
    report["executionMode"] = "simulated"
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el informe simulado del piloto RAG.")
    parser.add_argument(
        "--prompt-version",
        choices=tuple(SYSTEM_PROMPTS),
        default=DEFAULT_PROMPT_VERSION,
        help=f"Version del prompt ({DEFAULT_PROMPT_VERSION} por defecto).",
    )
    args = parser.parse_args()
    print(json.dumps(evaluate_simulated(prompt_version=args.prompt_version), indent=2))


if __name__ == "__main__":
    main()
