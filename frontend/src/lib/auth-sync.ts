// Seguimiento de los cambios de sesión (login y logout), también entre pestañas.
// Solo se usa en el navegador.

export type AuthChange = "login" | "logout";

const CHANNEL_NAME = "synapdesk-auth";

// Aumenta con cada login o logout, propio o de otra pestaña. El cliente HTTP lo compara
// antes de reintentar una solicitud: si cambió, la sesión ya no es la misma.
let generation = 0;
const listeners = new Set<(change: AuthChange) => void>();
let channel: BroadcastChannel | null = null;

function getChannel(): BroadcastChannel | null {
  if (typeof window === "undefined" || typeof BroadcastChannel === "undefined") return null;
  if (!channel) {
    channel = new BroadcastChannel(CHANNEL_NAME);
    channel.onmessage = (event: MessageEvent<AuthChange>) => applyChange(event.data);
  }
  return channel;
}

function applyChange(change: AuthChange) {
  generation += 1;
  listeners.forEach((listener) => listener(change));
}

export function getAuthGeneration(): number {
  getChannel();
  return generation;
}

/** Registra un login o logout de esta pestaña y avisa a las demás. */
export function notifyAuthChange(change: AuthChange) {
  applyChange(change);
  getChannel()?.postMessage(change);
}

/** Escucha los cambios de sesión de esta y de otras pestañas. Devuelve la función para dejar de escuchar. */
export function onAuthChange(listener: (change: AuthChange) => void): () => void {
  getChannel();
  listeners.add(listener);
  return () => listeners.delete(listener);
}
