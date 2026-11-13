# Revisión ciega de relevancia del PR #32

Revisa las consultas contra las guías del corpus antes de abrir el informe de evaluación.
Marca cada caso como **cubierta**, **fuera de cobertura** o **ambigua**.
Si una guía ayuda a resolver o diagnosticar la consulta, anota su código.
Si varias son pertinentes, anota todas. Si falta contexto, registra cuál.

Persona que revisa

Fecha

| Caso | Consulta | Cobertura | Guías pertinentes | Motivo o contexto faltante |
|---|---|---|---|---|
| SUP-01 | En el equipo de recepción la intranet abre por dirección numérica, pero Windows dice que no encuentra el sitio al usar su nombre. ¿Qué reviso primero? | | | |
| SUP-02 | Cambiamos el computador de punto de red y quedó con la dirección del segmento anterior. ¿Cómo hago que Windows vuelva a solicitar una dirección automáticamente? | | | |
| SUP-03 | El documento sale de la cola y la impresora no muestra ningún aviso, pero nunca aparece la hoja. ¿Por dónde empiezo a revisar? | | | |
| SUP-04 | Docker Desktop dejó de arrancar tras reinstalar Windows y avisa que no detecta virtualización. ¿Cómo compruebo si está habilitada? | | | |
| SUP-05 | Necesito que los cambios en los registros DNS del dominio se reflejen en otro proveedor sin interrumpir el correo. ¿Cómo planifico el traspaso? | | | |
| SUP-06 | La impresora funciona y las páginas salen bien. ¿Cómo configuro que el escáner del equipo multifunción guarde los archivos directamente en una carpeta de red? | | | |
| SUP-07 | El contenedor ya funciona. Quiero automatizar la copia de sus volúmenes a otro servidor y conservar una copia diaria durante un mes. | | | |
| SUP-08 | WSL abre correctamente. Necesito exportar una distribución completa y restaurarla en el portátil de reemplazo conservando mis archivos. | | | |

## Guías del corpus

| Código | Guía |
|---|---|
| G01 | [Diagnosticar fallos de resolución DNS](https://learn.microsoft.com/es-es/troubleshoot/windows-client/networking/troubleshoot-dns-client-resolution-issues) |
| G02 | [Revisar IP y renovar una concesión DHCP](https://learn.microsoft.com/es-es/windows-server/administration/windows-commands/ipconfig) |
| G03 | [Diagnosticar desconexiones Wi-Fi](https://learn.microsoft.com/es-es/troubleshoot/windows-client/networking/wireless-network-connectivity-issues-troubleshooting) |
| G04 | [Investigar errores y tiempos de espera TCP/IP](https://learn.microsoft.com/es-es/troubleshoot/windows-client/networking/tcp-ip-connectivity-issues-troubleshooting) |
| G05 | [Comprobar acceso a un puerto o servicio](https://learn.microsoft.com/es-es/powershell/module/nettcpip/test-netconnection?view=windowsserver2025-ps) |
| G06 | [Diagnosticar una aplicación bloqueada al imprimir](https://learn.microsoft.com/es-es/troubleshoot/windows-server/printing/troubleshoot-printing-scenarios#failed-print-job) |
| G07 | [Diagnosticar el servicio Print Spooler detenido](https://learn.microsoft.com/es-es/troubleshoot/windows-server/printing/print-spooler-service-not-running) |
| G08 | [Investigar trabajos sin salida de impresión](https://learn.microsoft.com/es-es/troubleshoot/windows-server/printing/troubleshoot-printing-scenarios#no-print-output) |
| G09 | [Diagnosticar conexión RPC con impresoras compartidas](https://learn.microsoft.com/es-es/troubleshoot/windows-client/printing/windows-11-rpc-connection-updates-for-print) |
| G10 | [Localizar la causa de impresión lenta](https://learn.microsoft.com/es-es/troubleshoot/windows-server/printing/troubleshoot-printing-scenarios#slow-printing-or-unexpected-output) |
| G11 | [Preparar WSL y sus requisitos de instalación](https://learn.microsoft.com/es-es/windows/wsl/install) |
| G12 | [Consultar estado y actualizar WSL](https://learn.microsoft.com/es-es/windows/wsl/basic-commands#update-wsl) |
| G13 | [Diagnosticar virtualización requerida por Docker Desktop](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/topics/#docker-desktop-fails-due-to-virtualization-not-working) |
| G14 | [Resolver conflicto de puerto ocupado en Docker](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/topics/#port-already-allocated-errors) |
| G15 | [Diagnosticar rutas de carpetas montadas en Windows](https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/topics/#path-conversion-errors-on-windows) |

## Consultas reales anonimizadas

Usa esta plantilla para una muestra autorizada de consultas de soporte.
Conserva el síntoma técnico y elimina nombres, correos, identificadores, nombres de equipos y datos internos.
Usa identificadores nuevos que no revelen el número del ticket original.

| ID de evaluación | Consulta anonimizada | Cobertura | Guías pertinentes | Motivo o contexto faltante |
|---|---|---|---|---|
| REAL-01 | | | | |
