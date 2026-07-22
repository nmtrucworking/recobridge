import { proxyToRecommendationApi } from "../../_proxy";

export async function POST(request: Request) {
  return proxyToRecommendationApi(request, "/v1/events/exposure", { idempotent: true });
}
