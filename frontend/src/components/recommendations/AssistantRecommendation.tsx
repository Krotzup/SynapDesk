"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/Button";
import { SESSION_CHANGED } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { getFieldErrors, isApiError, isAuthenticationRequired } from "@/lib/errors";
import { recommendationsService } from "@/services/recommendations";
import { HumanReview, Recommendation, RecommendationStatus, ReviewDecision } from "@/types";
import { RecommendationSources } from "./RecommendationSources";

const statusLabels: Record<RecommendationStatus, string> = {
  pending: "Pendiente de revisión",
  accepted: "Aceptada",
  modified: "Modificada",
  rejected: "Rechazada",
};

const reviewedMessages: Record<RecommendationStatus, string> = {
  pending: "La recomendación está pendiente de revisión.",
  accepted: "La recomendación fue aceptada.",
  modified: "La recomendación fue modificada por un especialista.",
  rejected: "La recomendación fue descartada.",
};

const statusByDecision: Record<ReviewDecision, RecommendationStatus> = {
  accepted: "accepted",
  modified: "modified",
  rejected: "rejected",
};

type Mode = "view" | "edit" | "discard";
type Action = "edit" | "discard" | "generate";

interface ActionError {
  message: string;
  needsLogin: boolean;
}

const actionFallback: Record<Action, string> = {
  edit: "No se pudo guardar la recomendación editada. Intenta nuevamente.",
  discard: "No se pudo descartar la recomendación. Intenta nuevamente.",
  generate: "No se pudo generar una nueva recomendación. Intenta nuevamente.",
};

function actionErrorMessage(error: unknown, action: Action): string {
  const code = isApiError(error) ? error.error.code : null;
  switch (code) {
    case "AUTHENTICATION_REQUIRED":
      return "Tu sesión expiró. Inicia sesión de nuevo para continuar.";
    case "FORBIDDEN":
      return action === "generate"
        ? "No tienes permiso para generar recomendaciones."
        : "No tienes permiso para revisar recomendaciones.";
    case "RECOMMENDATION_NOT_FOUND":
    case "TICKET_NOT_FOUND":
      return "La recomendación o el ticket ya no existen. Recarga la página.";
    // Código propuesto al backend para una recomendación que ya tiene revisión.
    case "RECOMMENDATION_ALREADY_REVIEWED":
      return "Esta recomendación ya fue revisada. Recarga la página para ver su estado.";
    case "VALIDATION_ERROR":
      return "Revisa los datos ingresados.";
    // CSRF_INVALID llega aquí solo si también falló el único reintento de api.ts.
    case "CSRF_INVALID":
    case "ORIGIN_INVALID":
      return "No se pudo validar la solicitud. Recarga la página e intenta de nuevo.";
    case SESSION_CHANGED:
      return "La sesión cambió en otra pestaña. Revisa tu sesión e intenta de nuevo.";
    default:
      // SERVICE_UNAVAILABLE, otros 5xx y fallos de red.
      return actionFallback[action];
  }
}

const textareaClass =
  "w-full rounded-lg border bg-white px-3 py-2 text-xs text-[#1E293B] leading-relaxed placeholder-[#94A3B8] outline-none transition-colors focus:border-[#4338CA] focus:ring-2 focus:ring-[#4338CA]/20 disabled:bg-[#F8FAFC] resize-y";

function borderClass(hasError: boolean) {
  return hasError ? "border-[#EF4444]" : "border-[#C7D2FE]";
}

interface DemoState {
  /** Última recomendación y revisión registradas en la pestaña. */
  saved: { recommendation: Recommendation; review: HumanReview | null } | null;
  /** Acción en curso; sigue aquí aunque el panel que la inició ya no esté montado. */
  pending: Action | null;
}

/**
 * Solo con datos de ejemplo: el detalle se genera en el servidor, que no ve lo registrado en el
 * mock del navegador. Se guarda aquí por ticket, mientras dure la pestaña (se pierde al recargar,
 * igual que el mock), para que al volver al ticket se muestre lo ya revisado y no se ofrezca una
 * segunda revisión. Los paneles se suscriben: si se reabre el ticket mientras se guarda, el panel
 * nuevo muestra la acción en curso y se actualiza cuando termina. Con el backend real no se usa:
 * la página trae el estado del servidor.
 */
const demoStateByTicket = new Map<string, DemoState>();
const demoListeners = new Set<() => void>();

function updateDemoState(ticketId: string, change: Partial<DemoState>) {
  const current = demoStateByTicket.get(ticketId) ?? { saved: null, pending: null };
  // Objeto nuevo en cada cambio: useSyncExternalStore compara por referencia.
  demoStateByTicket.set(ticketId, { ...current, ...change });
  demoListeners.forEach((listener) => listener());
}

function subscribeDemoState(listener: () => void) {
  demoListeners.add(listener);
  return () => {
    demoListeners.delete(listener);
  };
}

// En el servidor y durante la hidratación no hay estado de la demo.
const noDemoState = () => undefined;

const editButtonId = "recommendation-edit-button";
const discardButtonId = "recommendation-discard-button";

interface AssistantRecommendationProps {
  ticketId: string;
  initialRecommendation: Recommendation | null;
}

/**
 * Última recomendación del ticket y acciones de revisión humana (Human-in-the-loop).
 * Editar registra una revisión "modified", Descartar una "rejected" y Reintentar pide una
 * nueva generación sin sobrescribir las anteriores.
 */
export function AssistantRecommendation({
  ticketId,
  initialRecommendation,
}: AssistantRecommendationProps) {
  const router = useRouter();
  // Con datos de ejemplo, el panel sigue lo registrado en la pestaña para este ticket (también
  // lo que termine de guardarse después de reabrirlo). En la primera carga no hay nada, así que
  // coincide con lo generado en el servidor.
  const demo = useSyncExternalStore(
    subscribeDemoState,
    () => (USE_MOCKS ? demoStateByTicket.get(ticketId) : undefined),
    noDemoState
  );
  const [localRecommendation, setRecommendation] = useState(initialRecommendation);
  // Revisión registrada en esta pestaña. Se guarda aparte para no sobrescribir el contenido
  // original generado por la IA (modelo de dominio).
  const [localReview, setReview] = useState<HumanReview | null>(null);
  const [localPending, setPending] = useState<Action | null>(null);
  const [mode, setMode] = useState<Mode>("view");
  const [draft, setDraft] = useState("");
  const [feedback, setFeedback] = useState("");
  const [contentError, setContentError] = useState<string | null>(null);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<ActionError | null>(null);

  const recommendation = demo?.saved ? demo.saved.recommendation : localRecommendation;
  const review = demo?.saved ? demo.saved.review : localReview;
  const pending = localPending ?? demo?.pending ?? null;
  const changedLocally = Boolean(demo?.saved);
  const contentRef = useRef<HTMLTextAreaElement>(null);
  const feedbackRef = useRef<HTMLTextAreaElement>(null);
  // Botón al que vuelve el foco al cancelar.
  const focusAfterCancel = useRef<string | null>(null);

  const busy = pending !== null;

  // Foco del teclado: al abrir el editor o el descarte va al primer campo; al cancelar vuelve
  // al botón que lo abrió.
  useEffect(() => {
    if (mode === "edit") contentRef.current?.focus();
    else if (mode === "discard") feedbackRef.current?.focus();
    else if (focusAfterCancel.current) {
      document.getElementById(focusAfterCancel.current)?.focus();
      focusAfterCancel.current = null;
    }
  }, [mode]);

  function resetForms() {
    setDraft("");
    setFeedback("");
    setContentError(null);
    setFeedbackError(null);
  }

  function startEdit() {
    if (!recommendation) return;
    resetForms();
    setActionError(null);
    setDraft(recommendation.content);
    setMode("edit");
  }

  function startDiscard() {
    resetForms();
    setActionError(null);
    setMode("discard");
  }

  function cancel() {
    focusAfterCancel.current = mode === "edit" ? editButtonId : discardButtonId;
    resetForms();
    setActionError(null);
    setMode("view");
  }

  // Con datos de ejemplo el detalle se genera en el servidor y no vería el cambio:
  // se actualiza aquí y se guarda para la navegación. Con el backend real se vuelve a pedir
  // la página.
  function afterSuccess(next: Recommendation, nextReview: HumanReview | null = null) {
    setRecommendation(next);
    setReview(nextReview);
    setMode("view");
    resetForms();
    if (USE_MOCKS) {
      updateDemoState(ticketId, { saved: { recommendation: next, review: nextReview } });
    } else {
      router.refresh();
    }
  }

  // La acción en curso se comparte con la demo para que un panel reabierto no la ofrezca de nuevo.
  function startPending(action: Action | null) {
    setPending(action);
    if (USE_MOCKS) updateDemoState(ticketId, { pending: action });
  }

  // Cada error de campo se muestra junto a su campo; si el backend devuelve varios, se
  // muestran todos.
  function handleError(error: unknown, action: Action) {
    const fields = getFieldErrors(error);
    const contentMessage = action === "edit" ? fields.modifiedContent : undefined;
    const feedbackMessage = action === "generate" ? undefined : fields.feedback;
    setContentError(contentMessage ?? null);
    setFeedbackError(feedbackMessage ?? null);
    if (contentMessage || feedbackMessage) {
      setActionError(null);
      return;
    }
    setActionError({
      message: actionErrorMessage(error, action),
      needsLogin: isAuthenticationRequired(error),
    });
  }

  async function submitReview(action: "edit" | "discard") {
    if (!recommendation || busy) return;

    const trimmedFeedback = feedback.trim();
    let submitted: HumanReview;
    if (action === "edit") {
      const content = draft.trim();
      if (!content) {
        setContentError("Escribe el texto de la recomendación.");
        return;
      }
      if (content === recommendation.content.trim()) {
        setContentError("No hiciste cambios. Edita el texto o cancela.");
        return;
      }
      submitted = { decision: "modified", modifiedContent: content };
    } else {
      submitted = { decision: "rejected" };
    }
    if (trimmedFeedback) submitted.feedback = trimmedFeedback;

    setContentError(null);
    setFeedbackError(null);
    setActionError(null);
    startPending(action);
    try {
      await recommendationsService.review(recommendation.id, submitted);
      // Solo cambia el estado: el contenido original se conserva.
      afterSuccess({ ...recommendation, status: statusByDecision[submitted.decision] }, submitted);
    } catch (error) {
      handleError(error, action);
    } finally {
      startPending(null);
    }
  }

  async function generate() {
    if (busy) return;
    setActionError(null);
    startPending("generate");
    try {
      afterSuccess(await recommendationsService.generate(ticketId));
    } catch (error) {
      handleError(error, "generate");
    } finally {
      startPending(null);
    }
  }

  const errorBox = actionError && (
    <div
      role="alert"
      className="text-xs text-[#B91C1C] bg-[#FEF2F2] border border-[#FECACA] rounded-xl px-3 py-2.5"
    >
      {actionError.message}{" "}
      {actionError.needsLogin && (
        <Link href="/login" className="font-medium underline">
          Ir al inicio de sesión
        </Link>
      )}
    </div>
  );

  const mockNotice = changedLocally && (
    <p className="text-[11px] text-[#92400E] bg-[#FEF3C7] border border-[#FDE68A] rounded-xl px-3 py-2">
      <strong>Datos de ejemplo:</strong> el cambio solo existe en esta pestaña y se pierde al
      recargar. Con el backend real quedará registrado junto con su revisor.
    </p>
  );

  const generateButton = (label: string) => (
    <Button type="button" variant="secondary" fullWidth disabled={busy} onClick={generate}>
      {pending === "generate" ? "Generando recomendación…" : label}
    </Button>
  );

  if (!recommendation) {
    return (
      <div className="space-y-3">
        <p className="text-xs text-[#64748B]">Aún no hay recomendaciones para este ticket.</p>
        {errorBox}
        {generateButton("Generar recomendación")}
      </div>
    );
  }

  const isPending = recommendation.status === "pending";
  const modifiedContent =
    recommendation.status === "modified" ? review?.modifiedContent : undefined;

  return (
    <div className="space-y-5" aria-busy={busy}>
      <div>
        <div className="flex items-center justify-between gap-2 mb-1.5">
          <p className="text-xs font-bold text-[#4338CA]">Recomendación generada</p>
          <span className="text-[11px] font-semibold text-[#4338CA] bg-[#E0E7FF] px-2 py-0.5 rounded-full">
            {statusLabels[recommendation.status]}
          </span>
        </div>

        {mode === "edit" && isPending ? (
          <div className="space-y-1.5">
            <label htmlFor="recommendation-content" className="sr-only">
              Texto de la recomendación
            </label>
            <textarea
              id="recommendation-content"
              ref={contentRef}
              rows={8}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              disabled={busy}
              aria-invalid={Boolean(contentError)}
              aria-describedby={contentError ? "recommendation-content-error" : undefined}
              className={`${textareaClass} ${borderClass(Boolean(contentError))}`}
            />
            {contentError && (
              <p id="recommendation-content-error" className="text-xs text-[#EF4444]">
                {contentError}
              </p>
            )}
          </div>
        ) : modifiedContent ? (
          <div className="space-y-2">
            <div className="rounded-xl border border-[#C7D2FE] bg-white px-3 py-2.5">
              <p className="text-[11px] font-semibold text-[#4338CA] mb-1">
                Versión modificada por el especialista
              </p>
              <p className="text-xs text-[#1E293B] leading-relaxed whitespace-pre-line">
                {modifiedContent}
              </p>
            </div>
            <details className="text-xs">
              <summary className="cursor-pointer text-[11px] font-medium text-[#4338CA]">
                Ver la recomendación original generada por la IA
              </summary>
              <p className="mt-1.5 text-[#475569] leading-relaxed whitespace-pre-line">
                {recommendation.content}
              </p>
            </details>
          </div>
        ) : (
          <>
            <p className="text-xs text-[#1E293B] leading-relaxed whitespace-pre-line">
              {recommendation.content}
            </p>
            {recommendation.status === "modified" && (
              <p className="mt-1.5 text-[11px] text-[#64748B]">
                Este es el texto original generado por la IA. La versión del especialista se
                mostrará cuando el backend entregue las revisiones de la recomendación.
              </p>
            )}
          </>
        )}
      </div>

      <RecommendationSources sources={recommendation.sources} />

      {mockNotice}

      {/* Acciones Human-in-the-loop: solo para recomendaciones sin revisar */}
      {isPending ? (
        <div className="pt-2 border-t border-[#C7D2FE] space-y-2">
          {mode === "view" && (
            <>
              <p className="text-xs font-bold text-[#4338CA] mb-2">Acciones sugeridas</p>
              {errorBox}
              <Button
                type="button"
                variant="accept"
                fullWidth
                disabled
                aria-describedby="accept-note"
              >
                ✓ Aceptar y resolver
              </Button>
              <p id="accept-note" className="text-[11px] text-[#64748B]">
                Disponible cuando el backend defina la operación para aceptar la recomendación y
                resolver el ticket a la vez.
              </p>
              <Button
                type="button"
                variant="secondary"
                fullWidth
                disabled={busy}
                id={editButtonId}
                onClick={startEdit}
              >
                ✏️ Editar
              </Button>
              <Button type="button" variant="ghost" fullWidth disabled={busy} onClick={generate}>
                {pending === "generate" ? "Generando recomendación…" : "🔄 Reintentar"}
              </Button>
              <Button
                type="button"
                variant="danger"
                fullWidth
                disabled={busy}
                id={discardButtonId}
                onClick={startDiscard}
              >
                🗑️ Descartar
              </Button>
            </>
          )}

          {mode !== "view" && (
            <form
              noValidate
              className="space-y-2"
              onSubmit={(event) => {
                event.preventDefault();
                submitReview(mode);
              }}
            >
              <p className="text-xs font-bold text-[#4338CA]">
                {mode === "edit" ? "Editar recomendación" : "¿Descartar esta recomendación?"}
              </p>
              {mode === "discard" && (
                <p className="text-[11px] text-[#475569]">
                  Quedará registrada como rechazada y podrás generar una nueva.
                </p>
              )}
              <label htmlFor="review-feedback" className="block text-[11px] text-[#475569]">
                {mode === "edit" ? "¿Qué cambiaste? (opcional)" : "Motivo (opcional)"}
              </label>
              <textarea
                id="review-feedback"
                ref={feedbackRef}
                rows={3}
                value={feedback}
                onChange={(event) => setFeedback(event.target.value)}
                disabled={busy}
                aria-invalid={Boolean(feedbackError)}
                aria-describedby={feedbackError ? "review-feedback-error" : undefined}
                placeholder={
                  mode === "edit"
                    ? "Ej.: faltaba un paso para renovar la configuración de red."
                    : "Ej.: la recomendación no corresponde al problema del ticket."
                }
                className={`${textareaClass} ${borderClass(Boolean(feedbackError))}`}
              />
              {feedbackError && (
                <p id="review-feedback-error" className="text-xs text-[#EF4444]">
                  {feedbackError}
                </p>
              )}
              {errorBox}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="submit"
                  variant={mode === "edit" ? "primary" : "danger"}
                  disabled={busy}
                  className={mode === "discard" ? "border-[#FECACA]" : ""}
                >
                  {mode === "edit"
                    ? pending === "edit"
                      ? "Guardando…"
                      : "Guardar cambios"
                    : pending === "discard"
                      ? "Descartando…"
                      : "Descartar"}
                </Button>
                <Button type="button" variant="ghost" disabled={busy} onClick={cancel}>
                  Cancelar
                </Button>
              </div>
            </form>
          )}
        </div>
      ) : (
        <div className="pt-2 border-t border-[#C7D2FE] space-y-2">
          <p className="text-xs text-[#475569]">{reviewedMessages[recommendation.status]}</p>
          {review?.feedback && (
            <p className="text-xs text-[#475569]">
              <span className="font-semibold">
                {review.decision === "rejected" ? "Motivo:" : "Comentario del especialista:"}
              </span>{" "}
              <span className="whitespace-pre-line">{review.feedback}</span>
            </p>
          )}
          {recommendation.status === "rejected" && (
            <>
              {errorBox}
              {generateButton("Generar nueva recomendación")}
            </>
          )}
        </div>
      )}
    </div>
  );
}
