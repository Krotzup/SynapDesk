# Verificación final y ratificaciones del PR #60

20-11-2026. Registro de evidencia, **no aprobación de merge**.

Fuentes de la revisión:

- [Revisión sobre 49e88f1](https://github.com/Krotzup/SynapDesk/pull/60#issuecomment-7026299699).
- [Respuesta PO/backend y alcance vigente](https://github.com/Krotzup/SynapDesk/pull/60#issuecomment-7041283764).
- [Conformidad frontend sobre 607482a](https://github.com/Krotzup/SynapDesk/pull/60#issuecomment-7024398107).

## Checks del HEAD citado por el revisor

Se consultó GitHub para el SHA completo
`49e88f1920291e6c9595b0fe3073cef868d0306f`: las ejecuciones vigentes terminaron
correctamente. Las ejecuciones canceladas del workflow de autenticación fueron
reemplazadas, sin interpretar una cancelación como prueba aprobada.

| Verificación | Resultado y evidencia |
| --- | --- |
| Backend y frontend general | [Aprobados](https://github.com/Krotzup/SynapDesk/actions/runs/44641165237) |
| Frontend específico | [Aprobado](https://github.com/Krotzup/SynapDesk/actions/runs/44641165438) |
| ML | [Aprobado](https://github.com/Krotzup/SynapDesk/actions/runs/44641165221) |
| Unitarias, PostgreSQL, TLS, Alembic y documentación/contratos | [Aprobados en ejecución sustituta vigente](https://github.com/Krotzup/SynapDesk/actions/runs/44641217781) |

El nuevo HEAD que retire HU10 debe aprobar sus propios checks. Esta evidencia
no se transfiere automáticamente a otro SHA ni acredita modelos reales.

## Integración protegida

Se conservan sesión agente/administrador, credencial entre servicios, origen,
CSRF de escrituras, cookies y sello de ingreso. La lectura SSR puede omitir
Origin; si existe se valida. No se aceptan cabeceras de proxy como reemplazo
de SEC-01B. El verificador del ensayo sigue limitado a testing; estas pruebas
no aprueban una terminación TLS distinta en Render ni ingreso productivo.

Las pruebas PostgreSQL del ensayo se amplían para documentos y predicciones:
admin/agente, sello ausente, credencial de servicio inválida, sesión ausente o
revocada, origen ajeno, CSRF inválido y prohibición de gestión documental al
agente. RAG comprueba estas fronteras en listado, generación, detalle y revisión;
la aceptación conserva el estado del ticket. Búsqueda mantiene su prueba con
sesión/CSRF y revocación reales. Se usan proveedores sintéticos, sin llamadas
a Gemini ni inferencia del artefacto pendiente.

## Ratificación concreta requerida

Las propuestas de PO/backend se registraron en el
[contrato de entrega](../contratos/entrega-pendientes-v1.md). No son aprobación
general de todas las reglas que esa respuesta no menciona. Deben ratificarse
por sus responsables en el PR:

- [ ] PO/equipo: tabla de transiciones y `resolvedAt` al resolver/cerrar/reabrir.
- [ ] PO/equipo: `expectedStatus` opcional en API y enviado por frontend;
  `TICKET_STATE_CONFLICT` y `TICKET_TRANSITION_INVALID` con HTTP 409.
- [ ] PO/equipo: filtros AND, búsqueda literal y categorías/áreas confirmadas.
- [ ] PO/equipo: documentos `.txt`/`.md`, UTF-8, 64 KiB y límites de fragmentación.
- [ ] Equipo: mapeos explícitos tipo→categoría y cola→área, sin valores inventados.
- [ ] PO/equipo: ratificar la propuesta compatible con #59: aceptar registra
  revisión y no cambia el estado del ticket.
- [ ] Equipo/Felipe: confianza por objetivo y compatibilidad del adaptador.
- [ ] Felipe: revisión de tickets, identidad alternativa, rutas optativas,
  autenticación y SEC-01B; alternativa Render Free en etapa posterior.
- [ ] Revisor independiente: registrar aprobación formal del HEAD final.

La consulta al endpoint de reviews de GitHub devolvió una lista vacía durante
esta revisión. Los comentarios de conformidad no sustituyen esa aprobación.
Ni el autor del PR ni el agente completan casillas en nombre del PO, Felipe
o una persona revisora independiente.

HU10 se retira. Matriz, artefacto autorizado, consultas, mapeos, cuotas y memoria
se gestionan mediante la [matriz MLOps propuesta](../ml/matriz-mlops.md).
No se añaden nuevas funcionalidades ni se crean recursos de pago para cerrar
estas condiciones. El despliegue y las mediciones reales continúan como etapa
de habilitación, según la devolución recibida.

## Validación local de la corrección de alcance

Pasaron 50 integraciones PostgreSQL del ingreso local, RAG y entrega ML, con
Alembic `upgrade/current/heads/check` hasta 0008 y eliminación de la base temporal;
73 unitarias focalizadas de matriz, clasificación, ingreso y RAG; 54 de
componentes; 48 del protocolo. También pasaron build/TypeScript, ESLint,
Prettier y controles de documentación, workflow y secretos (cero hallazgos).
No se hicieron llamadas reales a Gemini, ni se cargó un Joblib no autorizado.
