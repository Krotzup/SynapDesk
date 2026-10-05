# Contrato inicial entre backend y Machine Learning

## Estado

**Provisional**

## Propósito

Este documento define el contrato inicial de integración entre el backend y los componentes de Machine Learning de SynapDesk.

Su objetivo es acordar los datos de entrada, las predicciones de salida, el control de versiones, la trazabilidad, el manejo de errores y las responsabilidades de cada componente antes de implementar la integración.

Este contrato podrá evolucionar cuando se seleccionen el dataset, las clases definitivas, el modelo y la estrategia de despliegue.

Las estructuras descritas representan funcionalidades previstas y no implican que el modelo o la integración ya se encuentren implementados.

## Alcance inicial

La primera integración permitirá analizar el contenido de un ticket para producir, cuando el modelo lo permita:

- una categoría estimada;
- una prioridad estimada;
- un área responsable estimada;
- niveles de confianza;
- información de identificación y versión del modelo.

La recuperación semántica, los embeddings, RAG y la generación de recomendaciones corresponden a etapas posteriores y no forman parte de esta primera inferencia de clasificación.

## Principios de integración

- El backend será el punto de entrada para las solicitudes realizadas por el frontend.
- El frontend no se comunicará directamente con el componente de Machine Learning.
- El backend validará los datos antes de solicitar una inferencia.
- Machine Learning no modificará directamente los registros de PostgreSQL.
- El backend será responsable de persistir las predicciones.
- Las predicciones automáticas se mantendrán separadas de los valores validados por una persona.
- Cada predicción deberá identificar el modelo y la versión utilizados.
- Los errores del modelo no deberán impedir que el ticket sea registrado.
- No se enviarán contraseñas, credenciales ni otros datos sensibles al modelo.
- Un notebook de experimentación no será considerado por sí solo un artefacto integrable.

## Flujo inicial

1. El frontend envía los datos del ticket al backend.
2. El backend valida y registra el ticket.
3. El backend prepara la entrada requerida por el componente de Machine Learning.
4. Machine Learning procesa el título y la descripción.
5. Machine Learning devuelve las predicciones y sus niveles de confianza.
6. El backend valida la respuesta.
7. El backend registra la predicción asociada al ticket.
8. El frontend recibe el ticket y la información de predicción permitida.
9. Una persona autorizada podrá validar o modificar los valores definitivos del ticket.

El registro del ticket no dependerá obligatoriamente del éxito de la inferencia.

## Entrada para clasificación

Estructura inicial prevista:

```json
{
  "requestId": "4762428a-c356-44d7-8f43-e48fc16e393a",
  "ticketId": "64f10aed-c41c-46a3-91dd-f2cbcd5eb79f",
  "title": "Equipo sin acceso a la red",
  "description": "El usuario informa que no puede conectarse a la red corporativa."
}