import { api } from "@/lib/api";
import { Metrics } from "@/types";

export const metricsService = {
  get: (): Promise<Metrics> => api.get("/metrics"),
};
