"""Adaptador del artefacto local autorizado y validación de su salida pública."""
import hashlib
import io
import json
import math
from threading import Lock

from app.recuperacion.servicio import ErrorRecuperacion

OBJETIVOS = {"clasificacion_sugerida", "prioridad_estimada", "area_responsable"}


class ServicioClasificacion:
    def __init__(self, config):
        if not config.classifier_model_path or not config.classifier_model_sha256:
            raise ValueError("Falta artefacto autorizado y SHA-256.")
        datos = config.classifier_model_path.read_bytes()
        self.digest = hashlib.sha256(datos).hexdigest()
        if self.digest != config.classifier_model_sha256:
            raise ValueError("El artefacto no coincide con su SHA-256.")
        import joblib
        from ml.predict_ticket import TicketClassifier
        # Se deserializan los mismos bytes verificados. Joblib exige un origen de confianza.
        self.model = TicketClassifier(joblib.load(io.BytesIO(datos)))
        artifact = self.model.artifact
        if set(artifact["models"]) != OBJETIVOS or any(
                not isinstance(artifact.get(k), str) or not artifact[k].strip()
                for k in ("model_name", "model_version")):
            raise ValueError("Artefacto incompleto.")
        self.categories = config.classifier_category_mapping
        self.areas = config.classifier_area_mapping
        self.lock = Lock()

    def huella(self, title, description):
        return hashlib.sha256(json.dumps([self.digest, title, description, self.categories, self.areas],
                                        sort_keys=True, ensure_ascii=False).encode()).hexdigest()

    def predecir(self, title, description):
        try:
            with self.lock:
                result = self.model.predict(title, description)
            predictions = result["predictions"]
            if set(predictions) != OBJETIVOS:
                raise ValueError
            for value in predictions.values():
                score = value["confidence"]
                if (not isinstance(value["label"], str) or not value["label"].strip()
                        or isinstance(score, bool) or not isinstance(score, (int, float))
                        or not math.isfinite(score) or not 0 <= score <= 1):
                    raise ValueError
            tipo, prioridad, area = (predictions[k] for k in
                ("clasificacion_sugerida", "prioridad_estimada", "area_responsable"))
            if prioridad["label"] not in {"low", "medium", "high"}:
                raise ValueError
            return {"predictedType": tipo["label"], "predictedCategory": self.categories.get(tipo["label"]),
                    "predictedPriority": prioridad["label"], "predictedArea": self.areas.get(area["label"]),
                    "suggestedQueue": area["label"], "confidence": None,
                    "confidences": {"type": tipo["confidence"], "priority": prioridad["confidence"],
                                    "queue": area["confidence"]},
                    "modelName": result["modelName"], "modelVersion": result["modelVersion"]}
        except Exception:
            raise ErrorRecuperacion("CLASSIFICATION_UNAVAILABLE", "No se pudo obtener una predicción válida.") from None
