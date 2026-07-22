import { proxyToRecommendationApi } from "../_proxy";

export async function GET(request: Request) {
  return proxyToRecommendationApi(request, "/v1/health/ready", { authenticated: false });
}
