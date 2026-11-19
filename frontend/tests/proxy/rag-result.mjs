// Diagnóstico del ensayo: conserva metadatos acotados y nunca cuerpos de error.
const errorCodes = new Set([
  "INSUFFICIENT_INFORMATION",
  "QUERY_TOKEN_LIMIT_EXCEEDED",
  "TICKET_INVALID",
  "GENERATION_INVALID",
  "GENERATION_UNAVAILABLE",
  "RECOMMENDATIONS_UNAVAILABLE",
  "SEARCH_PROFILE_STALE",
  "SEARCH_UNAVAILABLE",
  "SEARCH_NOT_READY",
  "AUTHENTICATION_REQUIRED",
  "FORBIDDEN",
  "CSRF_INVALID",
  "ORIGIN_INVALID",
]);

export async function readRagResponse(response, config) {
  const summary = {
    mode: config.ragMode ?? "live",
    expectedOutcome: config.ragExpectedOutcome ?? "draft",
    status: response.status(),
    errorCode: null,
    outcome: "error",
    responseJsonValid: false,
    reviewVerified: false,
  };
  let payload;
  try {
    payload = await response.json();
    summary.responseJsonValid = true;
  } catch {
    return { summary, payload: null, validContract: false };
  }
  if (payload?.error) {
    summary.errorCode = errorCodes.has(payload.error.code)
      ? payload.error.code
      : "UNEXPECTED_ERROR";
  }
  if (summary.status === 422 && summary.errorCode === "INSUFFICIENT_INFORMATION") {
    summary.outcome = "abstention";
  } else if (
    summary.status === 201 &&
    payload !== null &&
    typeof payload === "object" &&
    !Array.isArray(payload)
  ) {
    summary.outcome = "draft";
  }
  return { summary, payload, validContract: summary.outcome !== "error" };
}
