import { forwardSemanticSearch } from "@/lib/server/search-proxy";

export const runtime = "nodejs";

export async function POST(request: Request) {
  return forwardSemanticSearch(request, {
    backendUrl: process.env.BACKEND_INTERNAL_URL,
    publicOrigin: process.env.SEARCH_PUBLIC_ORIGIN,
    sessionCookieName: process.env.SEARCH_SESSION_COOKIE_NAME,
    allowHttpLocal: process.env.BACKEND_ALLOW_HTTP_LOCAL === "true",
  });
}
