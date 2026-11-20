import { api } from "@/lib/api";
import { USE_MOCKS } from "@/lib/config";
import { MlPrediction } from "@/types";

export const predictionsService = {
  get: (ticketId: string): Promise<MlPrediction | null> =>
    USE_MOCKS ? Promise.resolve(null) : api.get(`/tickets/${ticketId}/prediction`),
  generate: (ticketId: string): Promise<MlPrediction> =>
    api.post(`/tickets/${ticketId}/prediction`, {}),
};
