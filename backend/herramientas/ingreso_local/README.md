# Ensayo local de navegador y PostgreSQL

Composición explícita de **testing**, independiente de la fábrica productiva.
Recompone las piezas de MVP04/MVP06B sobre main 3580ac4b (MVP09). No valida
Render, HTTPS público, cookies Secure en Edge ni un bootstrap operativo.

La [guía local](../../../docs/guia-recorrido-local-mvp.md) contiene los pasos de
preparación y los requisitos de provisión administrativa. El
[verificador portable](verificar.py) no conoce rutas de otros worktrees ni carga
automáticamente sus archivos privados; se ejecuta desde backend:

```powershell
./.venv/Scripts/python.exe -B -m herramientas.ingreso_local.verificar --modo todo --playwright-module RUTA_PRIVADA_PLAYWRIGHT_CORE
```

Usar el intérprete ya preparado en la copia. `--env-file` permite leer en memoria
un archivo privado explícito; no lo copia, imprime ni lo versiona. La salida por
defecto es un directorio nuevo bajo artifacts/ de **esta** copia. Se rechazan
directorios existentes o externos. No instala Python, Node, Docker, Edge ni módulos.

## Componentes y límites

- [aplicacion.py](aplicacion.py): compone CSRF/login/me y POST/GET/PATCH de tickets
  con adaptadores existentes. No agrega rutas a app.aplicacion ni administración.
- [evidencia.py](evidencia.py), [protocolo.mjs](protocolo.mjs) y
  [servidor_next.mjs](servidor_next.mjs): IP observada en socket, HMAC independiente,
  audiencia, controles originales, nonce único y SEC-01B/TLS. Rechazan IP declarada,
  replay y manipulación. Solo un worker local y claves nuevas por ejecución.
- [demo.py](demo.py): base propia aleatoria en 5433, Alembic, cuentas efímeras,
  backend TLS y Next real. Edge obtiene sesiones sólo por login. Los checkpoints
  SQL usan una conexión independiente antes y después del cambio de estado.
- [browser-crud.mjs](../../../frontend/tests/proxy/browser-crud.mjs): formulario
  real, creación, listado, detalle, cambio de estado y recarga para admin/agent.
  Los negativos de HTTP crudo se distinguen de las interacciones de interfaz.

No usa respuestas mock, no fabrica sesiones, no desactiva TLS/Origin/CSRF,
no reintenta escrituras y no necesita ML. Las dos cuentas y doce tickets iniciales son
fixtures explícitas de una base testing desechable, **no** una vía de bootstrap
operativo. No copiar este seed a desarrollo o producción. Los tickets comprobados
como creación de navegador tienen UUID nuevos, distintos de esos seeds.

Al terminar elimina únicamente la base aleatoria y los procesos, certificados y
archivos privados que creó. Los contenedores existentes siguen ejecutándose.
Los reportes saneados permanecen fuera de Git. Un fallo de cierre/limpieza no se
considera éxito; Windows requiere permiso para cerrar los procesos propios.

La UI es la actual de main: listado paginado, formulario y TicketStatusControl.
Los filtros pendientes se anuncian explícitamente en este ensayo y una URL con
filtros no se interpreta como un listado filtrado. Las recomendaciones ausentes
no impiden leer ni cambiar el estado del ticket. El transporte conserva la política
de cookies de #30; no se importa la variante antigua de MVP07.
