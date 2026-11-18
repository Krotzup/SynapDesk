import { forwardSemanticSearch } from "@/lib/server/search-proxy";

export const runtime = "nodejs";

export async function POST(request: Request) {
  return forwardSemanticSearch(request, {
    publicOrigin: process.env.SEARCH_PUBLIC_ORIGIN,
    sessionCookieName: process.env.SEARCH_SESSION_COOKIE_NAME,
  });
}
