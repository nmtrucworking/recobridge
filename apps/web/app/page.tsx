"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { catalog, catalogById, Product, reasonLabels } from "../lib/catalog";

type Profile = {
  id: "mai" | "minh" | "guest";
  apiUserId: string | null;
  short: string;
  label: string;
  taste: string;
  fallbackIds: string[];
};

type RecommendationItem = {
  product_id: string;
  category_id?: string | null;
  price_bucket?: number | null;
  score: number;
  rank: number;
  reason_code: string | null;
};

type RecommendationResponse = {
  request_id: string;
  model_version: string;
  feature_version: string;
  strategy_used: string;
  degraded: boolean;
  items: RecommendationItem[];
  latency_ms: number;
};

type RankedProduct = Product & {
  score: number;
  reason: string;
};

const profiles: Profile[] = [
  {
    id: "mai",
    apiUserId: "10002945",
    short: "MA",
    label: "Mai Anh",
    taste: "Hồ sơ hành vi A · Synerise release",
    fallbackIds: ["sku_1048", "sku_2091", "sku_3314", "sku_4172"],
  },
  {
    id: "minh",
    apiUserId: "10005456",
    short: "MH",
    label: "Minh Hoàng",
    taste: "Hồ sơ hành vi B · Synerise release",
    fallbackIds: ["sku_5088", "sku_6270", "sku_7331", "sku_8406"],
  },
  {
    id: "guest",
    apiUserId: null,
    short: "AN",
    label: "Khách ẩn danh",
    taste: "Chưa có lịch sử mua sắm",
    fallbackIds: ["sku_2091", "sku_1048", "sku_7331", "sku_3314"],
  },
];

const fallbackProducts = (profile: Profile): RankedProduct[] =>
  profile.fallbackIds.flatMap((id, index) => {
    const product = catalogById.get(id);
    return product
      ? [{ ...product, score: 0.9 - index * 0.05, reason: "Danh sách dự phòng trên thiết bị" }]
      : [];
  });

const stableIndex = (value: string) =>
  [...value].reduce((total, character) => total + character.charCodeAt(0), 0) % catalog.length;

const hydrateProduct = (item: RecommendationItem): Product => {
  const known = catalogById.get(item.product_id);
  if (known) return known;
  const visual = catalog[stableIndex(item.product_id)];
  return {
    id: item.product_id,
    name: `SKU Synerise ${item.product_id}`,
    category: item.category_id ? `Danh mục ${item.category_id}` : "Danh mục chưa xác định",
    price: 0,
    priceLabel: item.price_bucket == null ? "Nhóm giá chưa xác định" : `Nhóm giá ${item.price_bucket}`,
    image: visual.image,
    accent: visual.accent,
  };
};

const hydrateProducts = (response: RecommendationResponse): RankedProduct[] =>
  response.items.map((item) => ({
    ...hydrateProduct(item),
    score: item.score,
    reason: reasonLabels[item.reason_code ?? ""] ?? "Được RecoEngine lựa chọn",
  }));

const formatPrice = (price: number) =>
  new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(price);

const displayPrice = (product: Product) => product.priceLabel ?? formatPrice(product.price);

async function postJson<T>(path: string, payload: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok) throw new Error(`API returned ${response.status}`);
  return response.json() as Promise<T>;
}

export default function Home() {
  const [activeId, setActiveId] = useState<Profile["id"]>("mai");
  const [cartCount, setCartCount] = useState(2);
  const [liked, setLiked] = useState<string[]>([]);
  const [toast, setToast] = useState("");
  const [engineStatus, setEngineStatus] = useState<"checking" | "ready" | "degraded" | "offline">("checking");
  const profile = useMemo(() => profiles.find((item) => item.id === activeId) ?? profiles[0], [activeId]);
  const [products, setProducts] = useState<RankedProduct[]>(() => fallbackProducts(profiles[0]));
  const [relatedProducts, setRelatedProducts] = useState<Product[]>(() => catalog.slice(1, 4));
  const [receipt, setReceipt] = useState({
    strategy: "connecting",
    model: "pending",
    latency: 0,
    request: "—",
    degraded: false,
  });
  const sessionId = useRef(`web-${crypto.randomUUID()}`);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const heroProduct = products[0] ?? fallbackProducts(profile)[0];

  const notify = (message: string) => {
    setToast(message);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 2600);
  };

  useEffect(() => {
    fetch("/api/health", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("offline");
        const result = await response.json() as { status: string };
        setEngineStatus(result.status === "ok" ? "ready" : "degraded");
      })
      .catch(() => setEngineStatus("offline"));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    postJson<RecommendationResponse>(
      "/api/recommendations",
      {
        user_id: profile.apiUserId,
        session_id: sessionId.current,
        context: { page_type: "home", device_type: "desktop" },
        top_k: 4,
        strategy: "hybrid",
      },
      controller.signal,
    )
      .then((response) => {
        const hydrated = hydrateProducts(response);
        if (hydrated.length === 0) throw new Error("empty catalog mapping");
        setProducts(hydrated);
        setReceipt({
          strategy: response.strategy_used,
          model: response.model_version,
          latency: response.latency_ms,
          request: response.request_id,
          degraded: response.degraded,
        });
        setEngineStatus(response.degraded ? "degraded" : "ready");
        notify(`Đã tải gợi ý từ API cho ${profile.label}`);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setProducts(fallbackProducts(profile));
        setReceipt({ strategy: "local_fallback", model: "unavailable", latency: 0, request: "—", degraded: true });
        setEngineStatus("offline");
        notify("API tạm thời không phản hồi · đang dùng danh sách dự phòng");
      });
    return () => controller.abort();
  }, [profile]);

  useEffect(() => {
    if (receipt.request === "—" || products.length === 0) return;
    const frame = window.requestAnimationFrame(() => {
      void postJson("/api/events/exposure", {
        request_id: receipt.request,
        user_id: profile.apiUserId,
        session_id: sessionId.current,
        widget_id: "homepage-top-n",
        page_type: "home",
        occurred_at: new Date().toISOString(),
        items: products.map((product, index) => ({ product_id: product.id, position: index + 1 })),
      }).catch(() => undefined);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [products, profile.apiUserId, receipt.request]);

  useEffect(() => () => {
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
  }, []);

  const selectProfile = (id: Profile["id"]) => {
    setReceipt((current) => ({ ...current, strategy: "loading", request: "—" }));
    setActiveId(id);
  };

  const trackFeedback = (product: Product, eventType: "click" | "add_to_cart") => {
    if (receipt.request === "—") return;
    void postJson("/api/events/feedback", {
      request_id: receipt.request,
      user_id: profile.apiUserId,
      session_id: sessionId.current,
      product_id: product.id,
      event_type: eventType,
      occurred_at: new Date().toISOString(),
    }).catch(() => notify("Thao tác đã hoàn tất nhưng chưa đồng bộ được sự kiện"));
  };

  const addToCart = (product: Product) => {
    setCartCount((count) => count + 1);
    trackFeedback(product, "add_to_cart");
    notify(`Đã thêm ${product.name} · event add_to_cart đã được gửi`);
  };

  const toggleLike = (product: Product) => {
    setLiked((items) => items.includes(product.id) ? items.filter((item) => item !== product.id) : [...items, product.id]);
    trackFeedback(product, "click");
  };

  const refreshRelated = () => {
    postJson<RecommendationResponse>("/api/recommendations/related", { product_id: heroProduct.id, top_k: 3 })
      .then((response) => {
        const related = response.items.flatMap((item) => {
          return [hydrateProduct(item)];
        });
        if (related.length) setRelatedProducts(related);
        notify("Đã làm mới sản phẩm liên quan từ API");
      })
      .catch(() => notify("Chưa thể làm mới sản phẩm liên quan"));
  };

  const statusLabel = engineStatus === "ready"
    ? "RecoEngine sẵn sàng"
    : engineStatus === "degraded"
      ? "RecoEngine đang fallback"
      : engineStatus === "offline"
        ? "RecoEngine ngoại tuyến"
        : "Đang kiểm tra RecoEngine";

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="RecoBridge — Trang chủ">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span>RecoBridge</span>
        </a>
        <nav className="main-nav" aria-label="Điều hướng chính">
          <a className="active" href="#discover">Khám phá</a><a href="#recommendations">Dành cho bạn</a><a href="#how-it-works">Cách hoạt động</a>
        </nav>
        <div className="header-actions">
          <span className={`engine-status ${engineStatus}`}><i /> {statusLabel}</span>
          <button className="icon-button" aria-label="Tìm kiếm">⌕</button>
          <button className="cart-button" aria-label={`Giỏ hàng, ${cartCount} sản phẩm`}>Giỏ hàng <span>{cartCount}</span></button>
        </div>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <div className="eyebrow"><span>01</span> Khám phá theo cách của bạn</div>
          <h1>Gu của bạn,<br /><em>được hiểu đúng.</em></h1>
          <p>RecoBridge kết nối từng tín hiệu nhỏ để đưa đúng món đồ đến bạn — nhanh, có lý do và không còn những gợi ý vô nghĩa.</p>
          <div className="hero-actions">
            <a className="primary-button" href="#recommendations">Xem gợi ý của tôi <span>↗</span></a>
            <a className="text-link" href="#how-it-works">Vì sao tôi thấy những món này? →</a>
          </div>
          <div className="hero-proof"><div><strong>200ms</strong><span>mục tiêu p95</span></div><div><strong>Top-N</strong><span>theo ngữ cảnh</span></div><div><strong>24/7</strong><span>fallback an toàn</span></div></div>
        </div>
        <div className="hero-visual" id="discover" style={{ "--accent": heroProduct.accent } as React.CSSProperties}>
          <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
          <div className="visual-label">Chọn riêng cho {profile.label.split(" ")[0]}</div>
          <div className="hero-product-image" style={{ backgroundImage: `url(${heroProduct.image})` }} role="img" aria-label={heroProduct.name} />
          <div className="match-badge"><span>Độ phù hợp</span><strong>{Math.round(heroProduct.score * 100)}%</strong></div>
          <div className="hero-product-card"><div><span>{heroProduct.category}</span><h2>{heroProduct.name}</h2><p>{displayPrice(heroProduct)}</p></div><button onClick={() => addToCart(heroProduct)} aria-label={`Thêm ${heroProduct.name} vào giỏ`}>+</button></div>
        </div>
      </section>

      <section className="persona-strip" aria-label="Chọn hồ sơ demo">
        <div className="persona-intro"><span>Trải nghiệm trực tiếp</span><strong>Đổi người dùng, đổi cả danh sách.</strong></div>
        <div className="persona-options" role="tablist" aria-label="Hồ sơ người dùng">
          {profiles.map((item) => (
            <button key={item.id} className={item.id === activeId ? "persona active" : "persona"} onClick={() => selectProfile(item.id)} role="tab" aria-selected={item.id === activeId}>
              <span className="avatar">{item.short}</span><span><strong>{item.label}</strong><small>{item.taste}</small></span><i aria-hidden="true" />
            </button>
          ))}
        </div>
      </section>

      <section className="recommendations section-shell" id="recommendations">
        <div className="section-heading">
          <div><div className="eyebrow"><span>02</span> RecoEngine đang chọn</div><h2>Dành riêng cho {profile.label.split(" ").slice(-1)[0]}</h2><p>{profile.id === "guest" ? "Chưa có lịch sử? Không sao — đây là những lựa chọn đang được yêu thích." : "Được xếp hạng từ hành vi gần đây, sở thích và ngữ cảnh hiện tại của bạn."}</p></div>
          <div className="api-receipt" title="Thông tin trực tiếp từ Recommendation API">
            <div><span className="pulse" /> API response {receipt.degraded ? "· fallback" : ""}</div>
            <dl><div><dt>strategy</dt><dd>{receipt.strategy}</dd></div><div><dt>latency</dt><dd>{receipt.latency} ms</dd></div><div><dt>request</dt><dd>{receipt.request}</dd></div></dl>
          </div>
        </div>
        <div className="product-grid">
          {products.map((product, index) => (
            <article className="product-card" key={`${profile.id}-${product.id}`}>
              <div className="product-image-wrap" style={{ "--card-accent": product.accent } as React.CSSProperties}>
                <span className="rank">0{index + 1}</span>
                <button className={liked.includes(product.id) ? "like active" : "like"} onClick={() => toggleLike(product)} aria-label={liked.includes(product.id) ? `Bỏ lưu ${product.name}` : `Lưu ${product.name}`}>{liked.includes(product.id) ? "♥" : "♡"}</button>
                <div className="product-image" style={{ backgroundImage: `url(${product.image})` }} role="img" aria-label={product.name} />
                <button className="quick-add" onClick={() => addToCart(product)}>Thêm nhanh <span>+</span></button>
              </div>
              <div className="product-meta"><div><span>{product.category}</span><span>{Math.round(product.score * 100)}% match</span></div><h3>{product.name}</h3><p>{displayPrice(product)}</p><small><i /> {product.reason}</small></div>
            </article>
          ))}
        </div>
      </section>

      <section className="explain-section" id="how-it-works">
        <div className="explain-card">
          <div className="explain-copy"><div className="eyebrow light"><span>03</span> Minh bạch từ đầu</div><h2>Mỗi gợi ý đều có<br />một lý do.</h2><p>RecoBridge không chỉ trả về sản phẩm. Mỗi danh sách đi kèm chiến lược, phiên bản mô hình và mã lý do để trải nghiệm dễ hiểu, dễ kiểm chứng.</p><a href="#recommendations">Xem lại danh sách của bạn →</a></div>
          <div className="signal-flow" aria-label="Luồng tạo gợi ý"><div className="signal active"><span>01</span><div><strong>Tín hiệu</strong><small>click · giỏ hàng · mua</small></div></div><div className="connector"><i /></div><div className="signal"><span>02</span><div><strong>RecoEngine</strong><small>candidate · ranking · filter</small></div></div><div className="connector"><i /></div><div className="signal"><span>03</span><div><strong>Gợi ý</strong><small>cá nhân hóa · fallback</small></div></div></div>
        </div>
      </section>

      <section className="related section-shell">
        <div className="related-copy"><span className="mini-label">Khám phá thêm</span><h2>Những món đồ<br />hiểu nhau.</h2><p>Gợi ý liên quan theo danh mục, ngữ cảnh và độ tương đồng sản phẩm.</p><button onClick={refreshRelated}>Làm mới lựa chọn ↻</button></div>
        <div className="related-stage">
          {relatedProducts.map((product, index) => <div className={`related-item item-${index + 1}`} key={`related-${product.id}`}><div style={{ backgroundImage: `url(${product.image})` }} role="img" aria-label={product.name} /><span>{product.name}</span></div>)}
          <div className="related-center"><span>Seed item</span><strong>{heroProduct.id}</strong></div>
        </div>
      </section>

      <footer>
        <div className="footer-brand"><div className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span>RecoBridge</span></div><p>Kết nối dữ liệu, cá nhân hóa lựa chọn.</p></div>
        <div className="footer-links"><div><span>Sản phẩm</span><a href="#recommendations">Gợi ý</a><a href="#how-it-works">Cách hoạt động</a></div><div><span>Hệ thống</span><a href="#top">API v1</a><a href="#top">Model {receipt.model}</a></div></div>
        <div className="footer-status"><i /> {statusLabel}</div>
      </footer>

      <div className={toast ? "toast show" : "toast"} role="status" aria-live="polite"><span>✓</span>{toast}</div>
    </main>
  );
}
