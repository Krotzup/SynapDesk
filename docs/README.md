# Documentación de SynapDesk

La documentación técnica y funcional mantenida junto al código se organiza de la siguiente manera:

```text
docs/
├── arquitectura/   Diseño, límites, flujos y diagramas del sistema.
├── adr/            Registros de decisiones arquitectónicas.
├── contratos/      Acuerdos entre frontend, backend y Machine Learning.
└── gestion/        Convenciones, alcance y seguimiento técnico.
```

Los documentos deben actualizarse dentro del mismo pull request que modifica la decisión o el comportamiento correspondiente.

Documentos iniciales:

- [Estructura del repositorio](arquitectura/estructura-repositorio.md)
- [Estrategia de entornos](arquitectura/entornos.md)
- [Estrategia inicial de staging](arquitectura/staging.md)
- [Estrategia Git](gestion/estrategia-git.md)
- [Definición de Terminado](gestion/definicion-terminado.md)
- [Modelo inicial del dominio](arquitectura/modelo-dominio.md)
- [Contrato inicial entre frontend y backend](contratos/frontend-backend.md)