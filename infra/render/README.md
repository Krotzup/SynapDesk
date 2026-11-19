# Preparación para Render

El Blueprint raíz describe Next.js público y FastAPI privado con TLS directo.
**No se ha desplegado ni acreditado Render.** No hay credencial de Render ni
certificados de su hostname privado en el repositorio. `autoDeployTrigger: off`
evita publicar estos cambios al hacer push. Los planes son una propuesta de
staging; crear los servicios de pago requiere la cuenta y el presupuesto del equipo.

Referencias oficiales consultadas el 19 de noviembre de 2026:
[Blueprint](https://render.com/docs/blueprint-spec),
[despliegues](https://render.com/docs/deploys) y
[comprobaciones de salud](https://render.com/docs/health-checks).
El backend privado usa la comprobación TCP del proveedor; el frontend usa `/login`.
Estos checks no acreditan búsqueda, sesiones ni Gemini.

## Perfil ligero

Construir desde la raíz con `docker build -f infra/render/Dockerfile -t synapdesk-backend .`.
La imagen excluye `.env`, documentos privados, artefactos locales y claves.
Ejecuta como usuario sin privilegios y no instala torch.
El Blueprint deja IA y tickets HTTP apagados. Las rutas de login y `/auth/me`
siguen limitadas a la composición local de testing: antes de habilitar el
producto en Render se debe integrar la procedencia IP real y los adaptadores de
autenticación según AUTH-07. No usar el verificador del ensayo local en staging.

Preparar bases separadas para tickets y semántica, con pgvector y TLS verificado.
`POSTGRES_SSLMODE=verify-full` requiere la CA correspondiente, configurada en
libpq mediante `PGSSLROOTCERT` si no está en el almacén predeterminado.
Suministrar los valores privados en Render. Agregar los archivos secretos
`backend-cert.pem` y `backend-key.pem`, con SAN para el hostname privado real.
Configurar en Next.js `BACKEND_INTERNAL_URL=https://HOST_PRIVADO:10000` y la CA
de confianza mediante `NODE_EXTRA_CA_CERTS=/etc/secrets/backend-ca.pem`.
No usar `NODE_TLS_REJECT_UNAUTHORIZED=0`. La CA del servidor debe coincidir con
el certificado suministrado al backend.

Configurar `AUTH_INTERMEDIARIO`, `AUTH_ORIGENES_PERMITIDOS`, HMAC y límites del
contrato de autenticación; el bearer de Next.js debe coincidir con la política
del backend. Registrar el origen público exacto en `APPLICATION_PUBLIC_ORIGIN`.
Aplicar explícitamente `cd backend && alembic upgrade head` con la base correcta
y respaldo previo. La imagen incluye Alembic; no migra al arrancar.
El bootstrap del administrador se ejecuta por el procedimiento existente del
backend, con los pines y guardas de ese procedimiento.

## Perfil con IA

Construir la imagen con `--build-arg INCLUDE_ML=1`. Para Render se puede mantener
una variante de Dockerfile con el ARG fijado o desplegar una imagen preconstruida
privada. Antes de usarla, verificar que los wheels fijados existen para la
arquitectura elegida. No se descargaron ni construyeron estas dependencias de
Linux durante esta tarea. Medir RSS y latencia con una instancia y un worker;
el plan `starter` del perfil ligero no se considera suficiente para embeddings.
Elegir el plan según esa medición, sin derivar memoria de ejecución del tamaño
del paquete torch.

Entregar por un canal privado el artefacto del clasificador y su SHA-256; conservar
las versiones de scikit-learn de entrenamiento. El checksum identifica el archivo,
pero Joblib solo debe recibir artefactos de una procedencia de confianza.
Configurar `CLASSIFIER_MODEL_PATH`, `CLASSIFIER_MODEL_SHA256` y los mapeos
aprobados antes de `CLASSIFIER_ENABLED=true`.

Preparar el esquema semántico con `python -m ml.semantic_retrieval.cli init-db`
(consultar `--help` para conexión y confirmación), copiar el perfil V2 a una ruta
del servicio, configurar la base separada y habilitar búsqueda. Para carga web,
`DOCUMENTS_ENABLED=true` permite indexar incluso sin perfil de búsqueda, pero
la recuperación exige calibración V2 contra la revisión resultante del corpus.
Después de subir o retirar documentos, recalibrar con el conjunto de calibración,
conservar la evaluación reservada y reiniciar con el nuevo perfil. No actualizar
solo el número de revisión de un perfil antiguo.

Activar RAG únicamente con la configuración del contrato de recomendaciones,
incluida la decisión sobre datos externos. Verificar login, crear ticket,
predicción, carga, retiro, búsqueda, abstención y revisión humana desde el
frontend real. Las pruebas locales no sustituyen ese recorrido en Render.
