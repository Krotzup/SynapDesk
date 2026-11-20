"""Ingreso local, sesión y revisión RAG contra una base de ensayo aislada."""

import base64
import hmac
import json
import secrets
from time import time
from unittest.mock import patch
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import Request
from fastapi.testclient import TestClient
from pydantic import SecretBytes, SecretStr
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.cookies_auth import preparar_perfil
from app.configuracion import Configuracion
from app.persistencia.modelos.recomendacion import Recomendacion, RevisionRecomendacion
from app.persistencia.modelos.ticket import Ticket
from app.tickets.esquemas import TicketCreate
from herramientas.ingreso_local.aplicacion import crear_aplicacion_local
from herramientas.ingreso_local.evidencia import DOMINIO, VerificadorIngresoLocal, huella_controles
from pruebas.integracion.test_tickets import tickets  # noqa: F401
from pruebas.intermediario_auxiliar import ORIGEN, credencial, politica
from pruebas.login_auxiliar import configuracion_login


def test_generacion_y_revision_con_sesion_y_procedencia_reales(tickets, configuracion_bd_test):
    datos = configuracion_bd_test.model_dump()
    datos.update({k: v for k, v in configuracion_login().model_dump().items() if k.startswith("auth_")})
    servicio, clave, audiencia = credencial(), secrets.token_bytes(32), uuid4().hex
    datos.update(auth_intermediario=politica([servicio]), auth_origenes_permitidos=[ORIGEN],
                 auth_proxies_autorizados=["127.0.0.1/32"], auth_cookie_profile="local",
                 rag_enabled=True, search_enabled=True, rag_public_origin=ORIGEN,
                 rag_external_data_approved=True, gemini_api_key=SecretStr("clave-ficticia"))
    config = Configuracion(_env_file=None, **datos)
    perfil = preparar_perfil(config, origen_publico=ORIGEN,
        nombre_sesion="synapdesk_session_dev", nombre_contexto="synapdesk_csrf_context_dev")
    verificador = VerificadorIngresoLocal(config, SecretBytes(clave), audiencia,
        ventana_segundos=30, capacidad_nonces=64)
    app = crear_aplicacion_local(config, tickets["motor"], perfil, verificador,
        capacidad_argon2=1, max_cuerpo_bytes=65536, recuperacion=object())
    ticket = tickets["servicio"].crear(tickets["referencias"][1], TicketCreate(
        title="No resuelve el DNS", description="El equipo no puede resolver el nombre del servidor."))

    with TestClient(app, base_url="https://localhost", client=("127.0.0.1", 12345)) as cliente:
        def solicitar(ruta, metodo="GET", cuerpo=None, token=None, evidencia=True,
                      origen=ORIGEN, canal=True, sesion=True):
            headers = {"Authorization": "Bearer " + servicio.get_secret_value(),
                       "Origin": origen,
                       "Cookie": "synapdesk_session_dev=" +
                                 tickets["referencias"][1].credencial.get_secret_value()}
            if not canal:
                headers["Authorization"] = "Bearer credencial-invalida-de-prueba"
            if not sesion:
                headers["Cookie"] = ""  # No incorporar el cookie jar después de firmar.
            if token is not None:
                headers["X-CSRF-Token"] = token
            url = urlsplit(ruta)
            request = Request(dict(type="http", method=metodo, path=url.path,
                raw_path=url.path.encode(), query_string=url.query.encode(),
                headers=[(k.lower().encode(), v.encode()) for k, v in headers.items()]))
            payload = base64.urlsafe_b64encode(json.dumps(dict(
                v=1, aud=audiencia, ip="127.0.0.1", ts=int(time()), nonce=uuid4().hex,
                method=metodo, path=ruta, controls=huella_controles(request)),
                separators=(",", ":")).encode()).decode().rstrip("=")
            if evidencia:
                headers["X-SynapDesk-Ingress-Evidence"] = payload + "." + hmac.digest(
                    clave, DOMINIO + payload.encode(), "sha256").hex()
            return cliente.request(metodo, ruta, headers=headers, json=cuerpo)

        try:
            ruta = f"/api/v1/tickets/{ticket.id}/recommendations"
            assert solicitar(ruta, evidencia=False).status_code == 503
            assert solicitar(ruta).json() == []
            csrf = solicitar("/api/v1/auth/csrf")
            assert csrf.status_code == 200
            token = csrf.json()["csrfToken"]
            assert solicitar(ruta, "POST", {}, evidencia=False, token=token).status_code == 503
            assert solicitar(ruta, "POST", {}).status_code == 403
            with patch("app.api.recomendaciones.generar", return_value=None):
                abstencion = solicitar(ruta, "POST", {}, token=token)
            assert abstencion.status_code == 422
            assert abstencion.json()["error"]["code"] == "INSUFFICIENT_INFORMATION"
            assert abstencion.headers["cache-control"] == "no-store"
            assert solicitar(ruta).json() == []
            with Session(tickets["motor"]) as db:
                assert db.scalar(select(Recomendacion.id).where(Recomendacion.ticket_id == ticket.id)) is None
                assert db.get(Ticket, ticket.id).estado == "open"
            fuente = {"documentId": uuid4(), "documentChunkId": uuid4(),
                      "title": "Ayuda DNS", "excerpt": "Consultar DNS configurado.", "score": 0.8}
            with patch("app.api.recomendaciones.generar", return_value=("Consultar DNS configurado.", [fuente])):
                creada = solicitar(ruta, "POST", {}, token=token)
            assert creada.status_code == 201
            borrador = creada.json()
            assert borrador["status"] == "pending" and borrador["review"] is None
            assert borrador["sources"][0]["documentChunkId"] == str(fuente["documentChunkId"])
            assert [item["id"] for item in solicitar(ruta).json()] == [borrador["id"]]
            assert solicitar(f"/api/v1/recommendations/{borrador['id']}").json() == borrador
            for protegida, metodo, cuerpo in (
                (ruta, "GET", None), (ruta, "POST", {}),
                (f"/api/v1/recommendations/{borrador['id']}", "GET", None),
                (f"/api/v1/recommendations/{borrador['id']}/reviews", "POST", {"decision": "accepted"}),
            ):
                assert solicitar(protegida, metodo, cuerpo, token, evidencia=False).status_code == 503
                assert solicitar(protegida, metodo, cuerpo, token, canal=False).status_code == 503
                assert solicitar(protegida, metodo, cuerpo, token, sesion=False).status_code == 401
                assert solicitar(protegida, metodo, cuerpo, token, origen="https://ajeno.invalid").status_code == 403
                if metodo == "POST":
                    assert solicitar(protegida, metodo, cuerpo, "invalido").status_code == 403
            revisada = solicitar(f"/api/v1/recommendations/{borrador['id']}/reviews",
                "POST", {"decision": "accepted"}, token=token)
            assert revisada.status_code == 204
            assert solicitar(f"/api/v1/recommendations/{borrador['id']}/reviews",
                "POST", {"decision": "rejected"}, token=token).status_code == 409
            actual = solicitar(f"/api/v1/recommendations/{borrador['id']}").json()
            assert actual["status"] == "accepted" and actual["review"]["decision"] == "accepted"
            with Session(tickets["motor"]) as db:
                assert db.get(Ticket, ticket.id).estado == "open"
        finally:
            with tickets["motor"].begin() as db:
                db.execute(delete(RevisionRecomendacion).where(
                    RevisionRecomendacion.recomendacion_id.in_(
                        select(Recomendacion.id).where(Recomendacion.ticket_id == ticket.id))))
                db.execute(delete(Recomendacion).where(Recomendacion.ticket_id == ticket.id))
