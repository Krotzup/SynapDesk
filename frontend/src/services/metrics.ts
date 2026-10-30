import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { metricsMock } from "@/mocks/metrics";
import { Metrics } from "@/types";

const metricsApi = {
  // Incluye los conteos por estado del menú lateral y del listado de tickets
  getSummary: (): Promise<Metrics> => api.get("/metrics/summary"),
};

export type MetricsService = typeof metricsApi;

export const metricsService: MetricsService = USE_MOCKS ? metricsMock : metricsApi;
