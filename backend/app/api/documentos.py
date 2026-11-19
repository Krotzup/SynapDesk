"""API de documentos; lecturas para agentes y gestión reservada a administradores."""
from uuid import UUID
from fastapi import APIRouter, Request, Response
from sqlalchemy.orm import Session
from app.documentos import COLUMNAS, MAX_UPLOAD_BYTES, conexion_documentos, ingresar, representar
from app.persistencia.modelos import Usuario
from app.recuperacion.servicio import ErrorRecuperacion
from app.recomendaciones.acceso import identidad_aplicacion

router = APIRouter()


def administrador(request):
    identity = identidad_aplicacion(request, escritura=True)
    if identity.role != "admin":
        raise ErrorRecuperacion("FORBIDDEN", "Solo un administrador puede gestionar documentos.", 403)
    return identity


@router.get("/documents")
def listar(request: Request, response: Response, page: int = 1, pageSize: int = 20):
    response.headers["Cache-Control"] = "no-store"
    identidad_aplicacion(request, escritura=False)
    if (page < 1 or not 1 <= pageSize <= 100 or set(request.query_params) - {"page", "pageSize"}
            or any(len(request.query_params.getlist(k)) != 1 for k in request.query_params)):
        raise ErrorRecuperacion("VALIDATION_ERROR", "Revisa la paginación.", 422)
    with conexion_documentos(request.app.state.configuracion) as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        total = db.execute("SELECT count(*) FROM semantic_uploaded_documents WHERE retired_at IS NULL").fetchone()[0]
        offset = (page - 1) * pageSize
        rows = [] if offset > 2**63 - 1 else db.execute(
            f"SELECT {COLUMNAS} FROM semantic_uploaded_documents WHERE retired_at IS NULL "
            "ORDER BY created_at DESC,id DESC LIMIT %s OFFSET %s", (pageSize, offset)).fetchall()
        return {"items": [representar(row) for row in rows], "page": page, "pageSize": pageSize,
                "totalItems": total, "totalPages": (total + pageSize - 1) // pageSize}


@router.get("/documents/{document_id}")
def obtener(document_id: UUID, request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    identidad_aplicacion(request, escritura=False)
    with conexion_documentos(request.app.state.configuracion) as db:
        row = db.execute(f"SELECT {COLUMNAS} FROM semantic_uploaded_documents "
                         "WHERE id=%s AND retired_at IS NULL", (document_id,)).fetchone()
        if row is None:
            raise ErrorRecuperacion("DOCUMENT_NOT_FOUND", "El documento no existe.", 404)
        return representar(row)


@router.post("/documents", status_code=201)
async def subir(request: Request, response: Response):
    response.headers["Cache-Control"] = "no-store"
    from starlette.concurrency import run_in_threadpool
    identity = await run_in_threadpool(administrador, request)
    config = request.app.state.configuracion
    if not config.documents_enabled:
        raise ErrorRecuperacion("DOCUMENTS_UNAVAILABLE", "La carga de documentos está deshabilitada.")
    if not request.headers.get("content-type", "").lower().startswith("multipart/form-data;"):
        raise ErrorRecuperacion("VALIDATION_ERROR", "La carga requiere multipart/form-data.", 422)
    # Límite antes del parser multipart; incluye margen para metadatos y cabeceras.
    parts, size = [], 0
    async for part in request.stream():
        size += len(part)
        if size > MAX_UPLOAD_BYTES + 8192:
            raise ErrorRecuperacion("DOCUMENT_TOO_LARGE", "El archivo supera el límite permitido.", 413)
        parts.append(part)
    request._body = b"".join(parts)
    from starlette.exceptions import HTTPException
    try:
        await request.form(max_files=1, max_fields=2, max_part_size=MAX_UPLOAD_BYTES + 8192)
    except HTTPException:
        raise ErrorRecuperacion("VALIDATION_ERROR", "El formulario de carga no es válido.", 422) from None
    async with request.form(max_files=1, max_fields=2, max_part_size=MAX_UPLOAD_BYTES + 8192) as form:
        if (not {"file", "title"} <= set(form) or set(form) - {"file", "title", "description"}
                or any(len(form.getlist(k)) != 1 for k in form)):
            raise ErrorRecuperacion("VALIDATION_ERROR", "Envía archivo, título y descripción sin duplicados.", 422)
        file, title, description = form["file"], form["title"], form.get("description", "")
        if (not hasattr(file, "read") or not isinstance(title, str) or not 1 <= len(title.strip()) <= 150
                or not isinstance(description, str) or len(description) > 2000
                or "\x00" in title + description):
            raise ErrorRecuperacion("VALIDATION_ERROR", "Revisa el archivo, título y descripción.", 422)
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        def ejecutar():
            # La identidad pública no contiene nombre/fechas: proyectar el usuario persistido.
            with Session(request.app.state.motor_bd) as db:
                user = db.get(Usuario, identity.id)
                if user is None:
                    raise ErrorRecuperacion("AUTHENTICATION_REQUIRED", "La sesión ya no es válida.", 401)
                author = {"id": str(user.id), "name": user.nombre, "email": user.correo,
                          "role": user.rol, "isActive": user.activo,
                          "createdAt": user.creado_en.isoformat(), "updatedAt": user.actualizado_en.isoformat()}
            indexador = getattr(request.app.state, "indexador", None) or request.app.state.recuperacion
            return ingresar(config, indexador, title=title.strip(),
                description=description.strip() or None, filename=file.filename or "", data=data, author=author)
        return await run_in_threadpool(ejecutar)


@router.delete("/documents/{document_id}", status_code=204)
def retirar(document_id: UUID, request: Request):
    identity = administrador(request)
    with conexion_documentos(request.app.state.configuracion) as db:
        row = db.execute("SELECT retired_at FROM semantic_uploaded_documents WHERE id=%s FOR UPDATE",
                         (document_id,)).fetchone()
        if row is None:
            raise ErrorRecuperacion("DOCUMENT_NOT_FOUND", "El documento no existe.", 404)
        if row[0] is None:
            db.execute("DELETE FROM semantic_prototype_chunks WHERE document_id=%s", (document_id,))
            db.execute("DELETE FROM semantic_prototype_document_metadata WHERE document_id=%s", (document_id,))
            db.execute("UPDATE semantic_uploaded_documents SET retired_at=clock_timestamp(), "
                       "updated_at=clock_timestamp(), retired_by=%s WHERE id=%s", (identity.id, document_id))
    return Response(status_code=204, headers={"Cache-Control": "no-store"})
