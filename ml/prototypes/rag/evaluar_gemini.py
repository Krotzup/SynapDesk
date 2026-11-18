"""Ejecuta un ensayo sintético de RAG con Gemini."""

import argparse
import json
import os
import socket
import ssl
from http.client import HTTPException
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .evaluar_rag import EVALUATION_CASES, evaluate_prompt
from .piloto_rag import Case
from .prompt_rag import DEFAULT_PROMPT_VERSION, SYSTEM_PROMPTS


MODEL = "gemini-3.5-flash-lite"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
REQUEST_TIMEOUT_SECONDS = 30
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "fragmentIds": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                },
                "required": ["text", "fragmentIds"],
            },
        },
    },
    "required": ["steps"],
}
TOKEN_COUNT_FIELDS = (
    "promptTokenCount",
    "cachedContentTokenCount",
    "candidatesTokenCount",
    "thoughtsTokenCount",
    "totalTokenCount",
)


class GeminiError(RuntimeError):
    """Fallo de transporte o de la respuesta de Gemini."""


def describe_transport_error(error: Exception, timeout_seconds: int) -> str:
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return f"Se agotó la espera de conexión o lectura ({timeout_seconds} s)."
    if isinstance(reason, socket.gaierror):
        return "No se pudo resolver el servidor de Gemini (DNS)."
    if isinstance(reason, ssl.SSLError):
        return "Falló la conexión HTTPS con Gemini (TLS)."
    if isinstance(reason, ConnectionError):
        return "La conexión con Gemini no se pudo establecer o se interrumpió."
    if isinstance(reason, HTTPException):
        return "La respuesta de Gemini se interrumpió antes de completarse."
    return "No se pudo completar la conexión con Gemini."


def complete_gemini(
    messages: list[dict[str, str]], *, api_key: str, timeout_seconds: int
) -> tuple[str, Optional[dict[str, int]]]:
    system, user = messages
    body = {
        "systemInstruction": {"parts": [{"text": system["content"]}]},
        "contents": [{"role": "user", "parts": [{"text": user["content"]}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseJsonSchema": RESPONSE_SCHEMA,
            "maxOutputTokens": 1024,
        },
    }
    request = Request(
        ENDPOINT, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"}
    )
    request.add_unredirected_header("x-goog-api-key", api_key)
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.load(response)
    except HTTPError as error:
        status = error.code
        error.close()
        raise GeminiError(f"Gemini devolvió HTTP {status}.") from None
    except (URLError, OSError, HTTPException) as error:
        raise GeminiError(describe_transport_error(error, timeout_seconds)) from None
    except (json.JSONDecodeError, UnicodeError):
        raise GeminiError("Gemini devolvió una respuesta ilegible.") from None

    try:
        candidate, = payload["candidates"]
        if candidate["finishReason"] != "STOP":
            raise GeminiError("Gemini no completó la generación.")
        text = "".join(
            part["text"]
            for part in candidate["content"]["parts"]
            if "text" in part and not part.get("thought")
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        raise GeminiError("Gemini devolvió una respuesta sin un candidato completo.") from None
    if not text.strip():
        raise GeminiError("Gemini devolvió un candidato sin texto.")

    metadata = payload.get("usageMetadata")
    counts = {}
    if isinstance(metadata, dict):
        for field in TOKEN_COUNT_FIELDS:
            count = metadata.get(field)
            if type(count) is int and count >= 0:
                counts[field] = count
    return text, counts or None


def evaluate_gemini(
    api_key: str,
    *,
    cases: tuple[Case, ...] = EVALUATION_CASES,
    timeout_seconds: int = REQUEST_TIMEOUT_SECONDS,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
) -> dict:
    token_counts = []
    called_cases = iter(case.id for case in cases if case.retrieved)

    def complete(messages: list[dict[str, str]]) -> str:
        case_id = next(called_cases)
        try:
            text, counts = complete_gemini(messages, api_key=api_key, timeout_seconds=timeout_seconds)
        except GeminiError as error:
            raise GeminiError(f"{case_id} · {error}") from None
        token_counts.append(counts)
        return text

    report = evaluate_prompt(
        complete,
        provider="Google Gemini API",
        model=MODEL,
        prompt_version=prompt_version,
        cases=cases,
    )
    report["executionMode"] = "api"
    report["requestTimeoutSeconds"] = timeout_seconds
    usage_by_call = iter(token_counts)
    for case in report["cases"]:
        case["usageMetadata"] = next(usage_by_call) if case["generatorCalled"] else None

    report["summary"]["callsWithUsageMetadata"] = sum(counts is not None for counts in token_counts)
    report["usageTotals"] = {
        field: sum(counts[field] for counts in token_counts)
        for field in TOKEN_COUNT_FIELDS
        if token_counts and all(counts is not None and field in counts for counts in token_counts)
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalua prompts RAG con Gemini y datos sinteticos.")
    parser.add_argument(
        "--case",
        choices=tuple(case.id for case in EVALUATION_CASES),
        help="Evalua solo el caso indicado, por ejemplo R01.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=REQUEST_TIMEOUT_SECONDS,
        help="Segundos de espera por conexion o lectura (30 por defecto).",
    )
    parser.add_argument(
        "--prompt-version",
        choices=tuple(SYSTEM_PROMPTS),
        default=DEFAULT_PROMPT_VERSION,
        help=f"Version del prompt ({DEFAULT_PROMPT_VERSION} por defecto).",
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout debe ser mayor que cero.")
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        parser.error("Configura GEMINI_API_KEY en el entorno.")

    try:
        cases = tuple(case for case in EVALUATION_CASES if args.case is None or args.case == case.id)
        report = evaluate_gemini(
            api_key, cases=cases, timeout_seconds=args.timeout, prompt_version=args.prompt_version
        )
    except GeminiError as error:
        parser.exit(1, f"Error: {error}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
