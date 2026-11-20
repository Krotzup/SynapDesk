"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { priorityLabels } from "@/components/ui/Badge";
import { USE_MOCKS } from "@/lib/config";
import { describeError, ErrorDescription } from "@/lib/errors";
import { ErrorReference } from "@/components/ui/ErrorReference";
import { predictionsService } from "@/services/predictions";
import { MlPrediction } from "@/types";

export function TicketPrediction({ ticketId }: { ticketId: string }) {
  const [prediction, setPrediction] = useState<MlPrediction | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ErrorDescription | null>(null);
  useEffect(() => {
    let active = true;
    predictionsService
      .get(ticketId)
      .then(
        (value) => {
          if (active) setPrediction(value);
        },
        (caught) => {
          if (active) setError(describeError(caught));
        }
      )
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [ticketId]);

  async function generate() {
    setBusy(true);
    setError(null);
    try {
      setPrediction(await predictionsService.generate(ticketId));
    } catch (caught) {
      setError(describeError(caught));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      aria-labelledby="prediccion-titulo"
      className="p-3 bg-white border border-[#C7D2FE] rounded-xl space-y-2 text-xs text-[#475569]"
      aria-busy={loading || busy}
    >
      <h3 id="prediccion-titulo" className="font-bold text-[#4338CA]">
        Clasificación estimada · Predicción IA
      </h3>
      <p>Es una estimación para revisión humana. No cambia los valores del ticket.</p>
      {loading ? (
        <p role="status">Consultando predicción…</p>
      ) : prediction ? (
        <>
          <dl className="space-y-1">
            <div>
              <dt className="inline font-semibold">Categoría: </dt>
              <dd className="inline">
                {prediction.predictedCategory ?? "Sin correspondencia definida"}
              </dd>
            </div>
            {prediction.predictedType && (
              <div>
                <dt className="inline font-semibold">Tipo sugerido: </dt>
                <dd className="inline">{prediction.predictedType}</dd>
              </div>
            )}
            <div>
              <dt className="inline font-semibold">Prioridad estimada: </dt>
              <dd className="inline">
                {prediction.predictedPriority
                  ? priorityLabels[prediction.predictedPriority]
                  : "No disponible"}
              </dd>
            </div>
            <div>
              <dt className="inline font-semibold">Área estimada: </dt>
              <dd className="inline">
                {prediction.predictedArea ?? "Sin correspondencia definida"}
              </dd>
            </div>
          </dl>
          {prediction.confidences && (
            <p>
              Probabilidad del modelo para prioridad:{" "}
              {(prediction.confidences.priority * 100).toFixed(1)} %. No equivale a una garantía de
              acierto.
            </p>
          )}
          <p className="text-[11px]">
            Modelo {prediction.modelName} · {prediction.modelVersion}
          </p>
        </>
      ) : (
        <p>
          {USE_MOCKS
            ? "La predicción requiere el backend y un modelo configurado."
            : "Este ticket aún no tiene una predicción."}
        </p>
      )}
      {error && (
        <div role="alert">
          <p>
            {error.message}{" "}
            {error.kind === "authentication" && (
              <Link href="/login" className="underline">
                Iniciar sesión
              </Link>
            )}
          </p>
          <ErrorReference requestId={error.requestId} />
        </div>
      )}
      {!USE_MOCKS && !loading && (
        <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={generate}>
          {busy ? "Estimando…" : "Estimar clasificación"}
        </Button>
      )}
    </section>
  );
}
