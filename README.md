# SynapDesk

**SynapDesk** es una plataforma inteligente de soporte TI orientada a optimizar la clasificación, priorización y asistencia en la resolución de tickets mediante la integración de **Machine Learning, recuperación semántica, Retrieval-Augmented Generation (RAG) y Large Language Models (LLM)**.

El proyecto busca transformar documentación técnica y tickets históricos en conocimiento útil para los agentes de soporte, reduciendo tareas repetitivas y facilitando el acceso a información relevante durante la atención de nuevas incidencias.

## Objetivo

Diseñar, desarrollar y evaluar una plataforma capaz de asistir a los equipos de soporte TI mediante un flujo inteligente que combine clasificación automática, recuperación de información y generación contextualizada de recomendaciones.

El flujo general del sistema es:

**Ticket → Machine Learning → Recuperación semántica → RAG → LLM → Recomendación → Validación humana**

## Funcionalidades principales

* Gestión de usuarios y roles.
* Creación y administración de tickets.
* Clasificación automática de incidencias mediante Machine Learning.
* Estimación de prioridad y categoría.
* Gestión de documentación técnica.
* Generación y almacenamiento de embeddings.
* Búsqueda semántica mediante base de datos vectorial.
* Recuperación de tickets históricos similares.
* Implementación de arquitectura RAG.
* Generación de recomendaciones mediante LLM.
* Visualización de las fuentes utilizadas.
* Validación Human-in-the-loop.
* Registro de resultados y métricas de evaluación.

## Tecnologías

### Frontend

* Next.js
* React
* Tailwind CSS

### Backend

* Python
* FastAPI
* Pydantic

### Base de datos

* PostgreSQL
* pgvector

### Inteligencia Artificial

* Scikit-learn
* PyTorch / TensorFlow
* Hugging Face
* Modelos de embeddings
* Large Language Models
* RAG

### Infraestructura y desarrollo

* Docker
* GitHub
* GitHub Projects
* Jupyter Notebook / Google Colab

## Arquitectura conceptual

```text
                    SynapDesk
                        │
             ┌──────────┴──────────┐
             │                     │
          Frontend              Backend
             │                     │
             └──────────┬──────────┘
                        │
            ┌───────────┼────────────┐
            │           │            │
            ▼           ▼            ▼
           ML          RAG          LLM
            │           │            │
            │      Embeddings        │
            │           │            │
            └───────────┼────────────┘
                        │
                PostgreSQL + pgvector
```

## Machine Learning

El componente de Machine Learning se utiliza principalmente para analizar los tickets recibidos y estimar atributos como:

* categoría;
* prioridad;
* área responsable.

Los diferentes modelos serán evaluados utilizando métricas como:

* Precision;
* Recall;
* Macro F1-Score;
* Weighted F1-Score;
* matriz de confusión.

## RAG y recuperación semántica

SynapDesk utiliza una arquitectura RAG para recuperar información relevante desde:

* documentación técnica;
* manuales;
* procedimientos;
* tickets históricos;
* soluciones anteriores.

La información recuperada es utilizada como contexto para el modelo de lenguaje, permitiendo generar recomendaciones basadas en fuentes disponibles dentro del sistema.

## Human-in-the-loop

Las recomendaciones generadas por inteligencia artificial no reemplazan la decisión del agente.

El usuario podrá:

* aceptar una recomendación;
* modificarla;
* rechazarla;
* consultar las fuentes utilizadas.

Este enfoque mantiene la supervisión humana dentro del proceso de resolución.

## Equipo

El proyecto es desarrollado por un equipo multidisciplinario de tres integrantes, con responsabilidades principales distribuidas entre:

* desarrollo Full Stack y arquitectura;
* Machine Learning y Deep Learning;
* desarrollo Frontend y experiencia de usuario;
* RAG y modelos de lenguaje;
* integración, pruebas y despliegue.

## Metodología

El desarrollo se organiza mediante **Scrum complementado con prácticas de MLOps ligero**, permitiendo trabajar de manera incremental y mantener trazabilidad sobre datasets, experimentos, modelos y métricas.

## Estado del proyecto

SynapDesk se encuentra actualmente en desarrollo como parte de un **Proyecto APT de Ingeniería Informática**.

El objetivo es obtener al finalizar el proyecto una versión:

* funcional;
* integrada;
* evaluada;
* documentada;
* contenerizada;
* desplegada en un ambiente demostrativo.

## Documentación del proyecto

La documentación técnica se mantiene versionada junto al código:

* [Organización de la documentación](docs/README.md)
* [Estructura inicial del repositorio](docs/arquitectura/estructura-repositorio.md)
* [Estrategia Git](docs/gestion/estrategia-git.md)
* [Definición de Terminado](docs/gestion/definicion-terminado.md)
* [Registros de decisiones arquitectónicas](docs/adr/)
* [Contratos de integración](docs/contratos/)

Las reglas para ramas, commits y pull requests se encuentran en [CONTRIBUTING.md](CONTRIBUTING.md).

## Evolución futura

Posterior al desarrollo y despliegue de la plataforma principal, se contempla como posible evolución la creación de una **API empresarial** que permita integrar las capacidades inteligentes de SynapDesk con plataformas externas como sistemas de mesa de ayuda o soluciones empresariales existentes.

Esta funcionalidad se considera una extensión futura y no forma parte del alcance principal del desarrollo actual.

## Licencia

La licencia del proyecto será definida de acuerdo con los criterios académicos y de propiedad intelectual establecidos por el equipo y la institución.
