import type { SearchService } from "@/services/search";
import type { SearchResponse } from "@/lib/search-contract";
import { SearchResult } from "@/types";
import { normalizeText } from "./tickets";
import { MOCK_ERROR_QUERY, rejectWithApiError, simulateLatency } from "./utils";

type Chunk = Omit<SearchResult, "score">;

const documents = {
  vpn: {
    documentId: "3f6b2c1e-8a47-4d2b-9c5e-1a7f0d3e6b21",
    title: "Guía de acceso remoto por VPN",
  },
  password: {
    documentId: "a91d4e72-5b3c-4f8a-b6e1-2c9d7f04a358",
    title: "Procedimiento de restablecimiento de contraseña",
  },
  printer: {
    documentId: "c47e19a3-2d6f-4b85-8e0c-9b3a1f52d764",
    title: "Solución de problemas de impresoras de red",
  },
  email: {
    documentId: "e25f8b06-7c1a-4e93-a4d2-6f0b3c81e957",
    title: "Configuración del correo corporativo en Outlook",
  },
  wifi: {
    documentId: "58c3a7d1-9e2b-4f60-bc84-d1e6a2079f3c",
    title: "Conectividad Wi-Fi en las oficinas",
  },
  software: {
    documentId: "7d0e5f94-3b8c-4a17-9f26-8c4b1e3d05a2",
    title: "Solicitud e instalación de software autorizado",
  },
};

const chunks: Chunk[] = [
  {
    ...documents.vpn,
    documentChunkId: "0b8e4c2a-6f13-4d9e-a7b5-3c1f9e08d264",
    excerpt:
      "Para conectarse a la VPN desde casa, abra el cliente de acceso remoto, seleccione el perfil corporativo e ingrese su usuario de red y el código del autenticador.",
  },
  {
    ...documents.vpn,
    documentChunkId: "9a2f7d1c-4e85-4b3a-8c06-e5b1d4f7a290",
    excerpt:
      "si la VPN se desconecta cada pocos minutos, verifique que la red de su casa no bloquee el puerto del túnel y reinstale el cliente con la versión publicada por TI.",
  },
  {
    ...documents.password,
    documentChunkId: "4c7b1e9f-2a3d-4f68-b5e0-7d9c2a1f8e43",
    excerpt:
      "El restablecimiento de contraseña se realiza desde el portal de autoservicio. La nueva contraseña debe tener al menos 12 caracteres y no repetir las últimas cinco.",
  },
  {
    ...documents.password,
    documentChunkId: "e1d9a3f5-7b2c-4e06-9a84-b6c3f0d71e52",
    excerpt:
      "cuando la cuenta queda bloqueada por intentos fallidos, el desbloqueo es automático a los 30 minutos o puede solicitarse a la mesa de ayuda con verificación de identidad.",
  },
  {
    ...documents.printer,
    documentChunkId: "6f3a8d2b-1c9e-4b75-a0d4-9e2f7c5b1a38",
    excerpt:
      "Si la impresora no imprime y los documentos quedan en cola, reinicie el servicio de cola de impresión y confirme que el equipo esté en la misma red que la impresora.",
  },
  {
    ...documents.printer,
    documentChunkId: "b5e2c7a9-3d1f-4a86-8b0e-2f6d9c4a7e15",
    excerpt:
      "Para agregar una impresora de red, use el nombre que aparece en la etiqueta del equipo; no instale controladores descargados desde sitios externos.",
  },
  {
    ...documents.email,
    documentChunkId: "2d7c9e4a-8b1f-4c53-9e6a-0a4b8d2f6c71",
    excerpt:
      "Si Outlook solicita la contraseña del correo de forma repetida, cierre la sesión de Office, elimine las credenciales guardadas y vuelva a iniciar sesión.",
  },
  {
    ...documents.email,
    documentChunkId: "f8a1b3d6-5e9c-4f27-a1c8-4d7e0b9f3a62",
    excerpt:
      "el buzón corporativo tiene un límite de 50 GB; al superarlo, el correo deja de enviar mensajes hasta archivar o eliminar elementos antiguos.",
  },
  {
    ...documents.wifi,
    documentChunkId: "a3c6e9f2-4b7d-4e18-b2a5-8f1c6d3e9b74",
    excerpt:
      "La red Wi-Fi corporativa requiere el certificado instalado por TI. Si el equipo no se conecta, olvide la red, reinicie el adaptador y vuelva a conectarse con su usuario.",
  },
  {
    ...documents.software,
    documentChunkId: "c9f4b2e7-6a3d-4c81-9d5f-1e8a7b3c0d46",
    excerpt:
      "La instalación de software se solicita mediante un ticket indicando el programa, la versión y el motivo; solo se instala software del catálogo autorizado.",
  },
];

// Palabras frecuentes que no aportan a la coincidencia.
const STOPWORDS = new Set([
  "como",
  "con",
  "cual",
  "del",
  "desde",
  "las",
  "los",
  "mas",
  "mis",
  "para",
  "pero",
  "por",
  "que",
  "una",
  "uno",
]);

// Raíz aproximada para que "conectar", "conectarse" y "conecta" coincidan.
function stem(word: string): string {
  return word.slice(0, 6);
}

function tokenize(text: string): Set<string> {
  const words = normalizeText(text).match(/[\p{L}\p{N}]+/gu) ?? [];
  return new Set(words.filter((word) => word.length >= 3 && !STOPWORDS.has(word)).map(stem));
}

/**
 * Similitud SIMULADA: proporción de palabras de la consulta presentes en el título o
 * el fragmento, llevada a un rango parecido al de la similitud coseno (0,30 a 0,95).
 * No representa el comportamiento del modelo de embeddings; solo ordena los ejemplos.
 */
function simulatedScore(queryTokens: Set<string>, chunk: Chunk): number {
  const chunkTokens = tokenize(`${chunk.title} ${chunk.excerpt}`);
  const matches = [...queryTokens].filter((token) => chunkTokens.has(token)).length;
  if (matches === 0) return 0;
  return Math.round((0.3 + 0.65 * (matches / queryTokens.size)) * 100) / 100;
}

export const searchMock: SearchService = {
  semantic: (query, limit = 5) => {
    if (normalizeText(query.trim()) === MOCK_ERROR_QUERY) {
      return rejectWithApiError(
        "SEARCH_UNAVAILABLE",
        "El servicio de búsqueda semántica no está disponible."
      );
    }

    const queryTokens = tokenize(query);
    const items = chunks
      .map((chunk) => ({ ...chunk, score: simulatedScore(queryTokens, chunk) }))
      .filter((item) => item.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);

    return simulateLatency<SearchResponse>({
      status: items.length ? "results" : "insufficient_information",
      items,
    });
  },
};
