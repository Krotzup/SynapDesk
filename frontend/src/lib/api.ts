import { ApiError } from "@/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions<TBody = unknown> {
  method?: HttpMethod;
  body?: TBody;
  headers?: Record<string, string>;
}

async function request<TResponse, TBody = unknown>(
  endpoint: string,
  options: RequestOptions<TBody> = {}
): Promise<TResponse> {
  const { method = "GET", body, headers = {} } = options;

  const config: RequestInit = {
    method,
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
  };

  if (body !== undefined) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, config);

  if (!response.ok) {
    const error: ApiError = await response
      .json()
      .catch(() => ({ message: "Error desconocido", statusCode: response.status }));
    throw error;
  }

  // 204 No Content
  if (response.status === 204) {
    return undefined as TResponse;
  }

  return response.json() as Promise<TResponse>;
}

export const api = {
  get: <TResponse>(endpoint: string, headers?: Record<string, string>) =>
    request<TResponse>(endpoint, { method: "GET", headers }),

  post: <TResponse, TBody = unknown>(endpoint: string, body: TBody) =>
    request<TResponse, TBody>(endpoint, { method: "POST", body }),

  put: <TResponse, TBody = unknown>(endpoint: string, body: TBody) =>
    request<TResponse, TBody>(endpoint, { method: "PUT", body }),

  patch: <TResponse, TBody = unknown>(endpoint: string, body: TBody) =>
    request<TResponse, TBody>(endpoint, { method: "PATCH", body }),

  delete: <TResponse>(endpoint: string) => request<TResponse>(endpoint, { method: "DELETE" }),
};
