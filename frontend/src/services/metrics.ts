import { api } from "@/lib/api";
import { Metrics } from "@/types";

export const metricsService = {
  getSummary: (): Promise<Metrics> => api.get("/metrics/summary"),
};
