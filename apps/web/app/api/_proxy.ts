const API_BASE_URL = (process.env.RECOMMENDATION_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const API_TOKEN = process.env.RECOMMENDATION_API_TOKEN ?? "recobridge-demo-token";

type ProxyOptions = {
  authenticated?: boolean;
  idempotent?: boolean;
};

export async function proxyToRecommendationApi(
  request: Request,
  path: string,
  options: ProxyOptions = {},
) {
  const headers = new Headers({ Accept: "application/json" });
  if (options.authenticated !== false) {
    headers.set("Authorization", `Bearer ${API_TOKEN}`);
  }

  const requestId = request.headers.get("x-request-id");
  if (requestId) headers.set("X-Request-ID", requestId);

  let body: string | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.text();
    headers.set("Content-Type", "application/json");
  }

  if (options.idempotent) {
    headers.set("Idempotency-Key", request.headers.get("idempotency-key") ?? crypto.randomUUID());
  }

  try {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: request.method,
      headers,
      body,
      signal: AbortSignal.timeout(5000),
    });
    const responseHeaders = new Headers({
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    });
    const upstreamRequestId = response.headers.get("x-request-id");
    if (upstreamRequestId) responseHeaders.set("X-Request-ID", upstreamRequestId);
    return new Response(response.body, { status: response.status, headers: responseHeaders });
  } catch {
    return Response.json(
      { error: { code: "UPSTREAM_UNAVAILABLE", message: "Recommendation API is unavailable", retryable: true } },
      { status: 502, headers: { "Cache-Control": "no-store" } },
    );
  }
}
