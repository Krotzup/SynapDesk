# Estructura inicial del repositorio

SynapDesk utiliza un monorepositorio para mantener coordinados frontend, backend, Machine Learning, infraestructura y documentación.

```text
SynapDesk/
├── backend/        Aplicación FastAPI y pruebas backend.
├── frontend/       Aplicación web Next.js.
├── ml/             Experimentación, entrenamiento y entrega de modelos.
├── infra/          Configuración local y futura configuración de despliegue.
├── docs/           Arquitectura, ADR, contratos y gestión técnica.
├── .github/        Plantillas y automatizaciones de GitHub.
├── .editorconfig   Convenciones básicas de edición.
├── .gitattributes  Normalización entre Windows y contenedores Linux.
├── .gitignore      Archivos que no deben versionarse.
└── README.md       Presentación general del proyecto.
```

## Criterios

- La raíz contiene únicamente elementos compartidos por el proyecto.
- Cada aplicación mantiene sus propias dependencias y pruebas.
- Los notebooks no forman parte del backend ejecutable.
- Los artefactos grandes de modelos y datasets no se incorporan directamente a Git.
- Los secretos se gestionan mediante variables de entorno no versionadas.
