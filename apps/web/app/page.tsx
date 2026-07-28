"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  catalog,
  categoryDisplayName,
  experience,
  fallbackProducts,
  fallbackRelated,
  hydrateProduct,
  Product,
  profiles,
  RankedProduct,
  reasonLabels,
} from "../lib/catalog";

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
  ranker_promoted: boolean;
  personalization_source: "session_feedback" | "historical_category_affinity" | "recent_popular" | "item_context";
  session_signal_count: number;
  dominant_category_id: string | null;
  items: RecommendationItem[];
  latency_ms: number;
};

type EngineStatus = "checking" | "ready" | "degraded" | "offline";
type OpenPanel = "search" | "cart" | null;
type CartLine = { product: Product; quantity: number };
type CartState = Record<string, CartLine>;
type FeedbackType = "click" | "add_to_cart" | "remove_from_cart";
type AdaptationState = {
  message: string;
  newProductIds: string[];
  signalCount: number;
};

const STORAGE_KEY = "recobridge-preferences-v1";
const emptyReceipt = {
  strategy: "Đang kết nối",
  model: "Chưa tải",
  latency: 0,
  request: null as string | null,
  degraded: false,
  rankerPromoted: false,
  personalizationSource: "recent_popular" as RecommendationResponse["personalization_source"],
  sessionSignalCount: 0,
  dominantCategoryId: null as string | null,
};

const strategyLabels: Record<string, string> = {
  baseline_session_adaptive: "Baseline thích nghi trong phiên",
  category_popular: "Baseline theo lịch sử danh mục",
  baseline_hybrid: "Baseline kết hợp",
  recent_popular: "Gợi ý theo xu hướng",
  item_similarity: "Tương đồng sản phẩm",
};

const formatPrice = (price: number) =>
  new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(price);

const displayPrice = (product: Product) => product.priceLabel ?? formatPrice(product.price);

const normalizeSearch = (value: string) =>
  value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("vi-VN").trim();

const getDeviceType = () => {
  if (window.matchMedia("(max-width: 560px)").matches) return "mobile";
  if (window.matchMedia("(max-width: 1024px)").matches) return "tablet";
  return "desktop";
};

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

function ProductVisual({ product, className }: { product: Product; className: string }) {
  const style = {
    "--visual-accent": product.accent,
    backgroundImage: product.image ? `url(${product.image})` : undefined,
  } as React.CSSProperties;

  return (
    <div
      className={`${className}${product.image ? " has-photo" : " generated-visual"}`}
      style={style}
      role="img"
      aria-label={product.name}
    >
      {!product.image && <span aria-hidden="true">{product.visualCode ?? product.category.slice(0, 2).toUpperCase()}</span>}
    </div>
  );
}

export default function Home() {
  const initialProfile = profiles.find((item) => item.id === experience.defaultProfileId) ?? profiles[0];
  const [activeId, setActiveId] = useState(initialProfile.id);
  const [products, setProducts] = useState<RankedProduct[]>(() => fallbackProducts(initialProfile));
  const [relatedProducts, setRelatedProducts] = useState<Product[]>(() => fallbackRelated(products[0]!));
  const [liked, setLiked] = useState<string[]>([]);
  const [cart, setCart] = useState<CartState>({});
  const [preferencesReady, setPreferencesReady] = useState(false);
  const [toast, setToast] = useState("");
  const [engineStatus, setEngineStatus] = useState<EngineStatus>("checking");
  const [isLoading, setIsLoading] = useState(true);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [isAdapting, setIsAdapting] = useState(false);
  const [adaptation, setAdaptation] = useState<AdaptationState | null>(null);
  const [receipt, setReceipt] = useState(emptyReceipt);
  const [openPanel, setOpenPanel] = useState<OpenPanel>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const sessionId = useRef("");
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);

  const profile = useMemo(
    () => profiles.find((item) => item.id === activeId) ?? initialProfile,
    [activeId, initialProfile],
  );
  const heroProduct = products[0] ?? fallbackProducts(profile)[0] ?? catalog[0]!;
  const cartItems = useMemo(() => Object.values(cart), [cart]);
  const cartCount = useMemo(() => cartItems.reduce((total, item) => total + item.quantity, 0), [cartItems]);
  const cartTotal = useMemo(
    () => cartItems.reduce((total, item) => total + item.product.price * item.quantity, 0),
    [cartItems],
  );
  const searchResults = useMemo(() => {
    const query = normalizeSearch(searchQuery);
    if (!query) return catalog;
    return catalog.filter((product) =>
      normalizeSearch(`${product.name} ${product.category} ${product.id}`).includes(query),
    );
  }, [searchQuery]);

  const notify = useCallback((message: string) => {
    setToast(message);
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 2600);
  }, []);

  const getSessionId = useCallback(() => {
    if (!sessionId.current) sessionId.current = `web-${crypto.randomUUID()}`;
    return sessionId.current;
  }, []);

  useEffect(() => {
    let savedProfileId: string | undefined;
    let savedLiked: string[] | undefined;
    let savedCart: CartState | undefined;
    try {
      const saved = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "{}") as {
        profileId?: string;
        liked?: string[];
        cart?: CartState;
      };
      if (saved.profileId && profiles.some((item) => item.id === saved.profileId)) savedProfileId = saved.profileId;
      if (Array.isArray(saved.liked)) savedLiked = saved.liked.filter((id) => typeof id === "string");
      if (saved.cart && typeof saved.cart === "object") savedCart = saved.cart;
    } catch {
      window.localStorage.removeItem(STORAGE_KEY);
    }
    const frame = window.requestAnimationFrame(() => {
      if (savedProfileId) setActiveId(savedProfileId);
      if (savedLiked) setLiked(savedLiked);
      if (savedCart) setCart(savedCart);
      setPreferencesReady(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!preferencesReady) return;
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify({ profileId: activeId, liked, cart }));
  }, [activeId, cart, liked, preferencesReady]);

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
        session_id: getSessionId(),
        context: { page_type: "home", device_type: getDeviceType() },
        top_k: experience.recommendationLimit,
        strategy: experience.strategy,
      },
      controller.signal,
    )
      .then((response) => {
        const hydrated = response.items.map((item) => ({
          ...hydrateProduct(item),
          score: item.score,
          reason: reasonLabels[item.reason_code ?? ""] ?? "Được RecoEngine lựa chọn",
        }));
        if (!hydrated.length) throw new Error("empty recommendations");
        setProducts(hydrated);
        setReceipt({
          strategy: response.strategy_used,
          model: response.model_version,
          latency: response.latency_ms,
          request: response.request_id,
          degraded: response.degraded,
          rankerPromoted: response.ranker_promoted,
          personalizationSource: response.personalization_source,
          sessionSignalCount: response.session_signal_count,
          dominantCategoryId: response.dominant_category_id,
        });
        setEngineStatus(response.degraded ? "degraded" : "ready");
        setRelatedProducts(fallbackRelated(hydrated[0]));
        void postJson<RecommendationResponse>("/api/recommendations/related", {
          product_id: hydrated[0].id,
          top_k: experience.relatedLimit,
        }).then((related) => {
          const next = related.items.map(hydrateProduct);
          if (next.length) setRelatedProducts(next);
        }).catch(() => undefined);
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        const fallback = fallbackProducts(profile);
        setProducts(fallback);
        setRelatedProducts(fallbackRelated(fallback[0]));
        setReceipt({
          ...emptyReceipt,
          strategy: "Gợi ý dự phòng",
          model: "Không khả dụng",
          degraded: true,
        });
        setEngineStatus("offline");
        notify("Không thể tải dữ liệu mới. Bạn vẫn có thể xem các gợi ý đã chuẩn bị sẵn.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  }, [profile, notify, getSessionId]);

  useEffect(() => {
    if (!receipt.request || !products.length || isLoading) return;
    const frame = window.requestAnimationFrame(() => {
      void postJson("/api/events/exposure", {
        request_id: receipt.request,
        user_id: profile.apiUserId,
        session_id: getSessionId(),
        widget_id: experience.widgetId,
        page_type: "home",
        occurred_at: new Date().toISOString(),
        items: products.map((product, index) => ({ product_id: product.id, position: index + 1 })),
      }).catch(() => undefined);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [isLoading, products, profile.apiUserId, receipt.request, getSessionId]);

  useEffect(() => {
    if (!openPanel) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusTimer = window.setTimeout(() => {
      if (openPanel === "search") searchInput.current?.focus();
      else closeButton.current?.focus();
    }, 0);
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpenPanel(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.clearTimeout(focusTimer);
      window.removeEventListener("keydown", closeOnEscape);
      document.body.style.overflow = previousOverflow;
    };
  }, [openPanel]);

  useEffect(() => () => {
    if (toastTimer.current) window.clearTimeout(toastTimer.current);
  }, []);

  const trackFeedback = async (product: Product, eventType: FeedbackType) => {
    if (!receipt.request || isAdapting) return;
    setIsAdapting(true);
    try {
      await postJson("/api/events/feedback", {
        request_id: receipt.request,
        user_id: profile.apiUserId,
        session_id: getSessionId(),
        product_id: product.id,
        event_type: eventType,
        occurred_at: new Date().toISOString(),
      });
      const response = await postJson<RecommendationResponse>("/api/recommendations", {
        user_id: profile.apiUserId,
        session_id: getSessionId(),
        context: { page_type: "home", device_type: getDeviceType() },
        top_k: experience.recommendationLimit,
        strategy: experience.strategy,
      });
      const previousIds = new Set(products.map((item) => item.id));
      const hydrated = response.items.map((item) => ({
        ...hydrateProduct(item),
        score: item.score,
        reason: reasonLabels[item.reason_code ?? ""] ?? "Được RecoEngine lựa chọn",
      }));
      if (!hydrated.length) throw new Error("empty adapted recommendations");

      setProducts(hydrated);
      setReceipt({
        strategy: response.strategy_used,
        model: response.model_version,
        latency: response.latency_ms,
        request: response.request_id,
        degraded: response.degraded,
        rankerPromoted: response.ranker_promoted,
        personalizationSource: response.personalization_source,
        sessionSignalCount: response.session_signal_count,
        dominantCategoryId: response.dominant_category_id,
      });
      setEngineStatus(response.degraded ? "degraded" : "ready");
      const newProductIds = hydrated.filter((item) => !previousIds.has(item.id)).map((item) => item.id);
      const signalLabel = eventType === "add_to_cart"
        ? "thêm vào giỏ"
        : eventType === "remove_from_cart"
          ? "bỏ khỏi giỏ"
          : "lưu sản phẩm";
      setAdaptation({
        message: `${signalLabel}: ${product.name} · ${categoryDisplayName(response.dominant_category_id ?? product.categoryId)}`,
        newProductIds,
        signalCount: response.session_signal_count,
      });
      setRelatedProducts(fallbackRelated(hydrated[0]));
      void postJson<RecommendationResponse>("/api/recommendations/related", {
        product_id: hydrated[0].id,
        top_k: experience.relatedLimit,
      }).then((related) => {
        const next = related.items.map(hydrateProduct);
        if (next.length) setRelatedProducts(next);
      }).catch(() => undefined);
      notify(
        response.personalization_source === "session_feedback"
          ? `Đã cập nhật ${newProductIds.length} lựa chọn từ tín hiệu mới.`
          : "Đã ghi nhận tín hiệu; sản phẩm này chưa có metadata trong model hiện tại.",
      );
    } catch {
      notify("Đã lưu thao tác trên thiết bị, nhưng chưa thể xếp hạng lại lúc này.");
    } finally {
      setIsAdapting(false);
    }
  };

  const selectProfile = (profileId: string) => {
    if (profileId === activeId) return;
    setIsLoading(true);
    setReceipt((current) => ({ ...current, strategy: "Đang cập nhật", request: null }));
    setAdaptation(null);
    setActiveId(profileId);
  };

  const addToCart = (product: Product) => {
    setCart((current) => ({
      ...current,
      [product.id]: { product, quantity: (current[product.id]?.quantity ?? 0) + 1 },
    }));
    void trackFeedback(product, "add_to_cart");
    notify(`Đã thêm ${product.name} vào giỏ hàng.`);
  };

  const updateQuantity = (productId: string, nextQuantity: number) => {
    const removedProduct = nextQuantity <= 0 ? cart[productId]?.product : undefined;
    setCart((current) => {
      const next = { ...current };
      if (nextQuantity <= 0) delete next[productId];
      else if (next[productId]) next[productId] = { ...next[productId], quantity: nextQuantity };
      return next;
    });
    if (removedProduct) void trackFeedback(removedProduct, "remove_from_cart");
  };

  const toggleLike = (product: Product) => {
    const isRemoving = liked.includes(product.id);
    setLiked((items) => isRemoving
      ? items.filter((item) => item !== product.id)
      : [...items, product.id]);
    if (isRemoving) notify(`Đã bỏ lưu ${product.name}.`);
    else void trackFeedback(product, "click");
  };

  const refreshRelated = () => {
    setRelatedLoading(true);
    postJson<RecommendationResponse>("/api/recommendations/related", {
      product_id: heroProduct.id,
      top_k: experience.relatedLimit,
    })
      .then((response) => {
        const related = response.items.map(hydrateProduct);
        if (related.length) setRelatedProducts(related);
        notify("Đã làm mới các sản phẩm liên quan.");
      })
      .catch(() => notify("Chưa thể làm mới lúc này. Vui lòng thử lại sau."))
      .finally(() => setRelatedLoading(false));
  };

  const strategyLabel = strategyLabels[receipt.strategy] ?? receipt.strategy;
  const personalizationModeLabel = receipt.personalizationSource === "session_feedback"
    ? "Theo tín hiệu phiên"
    : receipt.personalizationSource === "historical_category_affinity"
      ? "Theo lịch sử danh mục"
      : "Theo xu hướng";
  const statusLabel = isLoading
    ? "Đang chuẩn bị gợi ý"
    : isAdapting
      ? "Đang xếp hạng lại từ tín hiệu mới"
      : engineStatus === "ready" && receipt.personalizationSource === "session_feedback"
        ? "Baseline đang thích nghi trong phiên"
        : engineStatus === "ready"
          ? "Baseline theo lịch sử danh mục"
          : engineStatus === "degraded"
            ? "Đang dùng gợi ý theo xu hướng"
            : engineStatus === "offline"
              ? "Đang dùng gợi ý đã lưu"
              : "Đang kết nối";

  const closeNavigation = () => setMenuOpen(false);

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="RecoBridge — Trang chủ" onClick={closeNavigation}>
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span>RecoBridge</span>
        </a>
        <nav id="mobile-navigation" className={`main-nav${menuOpen ? " open" : ""}`} aria-label="Điều hướng chính">
          <a className="active" href="#discover" onClick={closeNavigation}>Khám phá</a>
          <a href="#recommendations" onClick={closeNavigation}>Dành cho bạn</a>
          <a href="#how-it-works" onClick={closeNavigation}>Cách hoạt động</a>
        </nav>
        <div className="header-actions">
          <span className={`engine-status ${isLoading ? "checking" : engineStatus}`}><i /> {statusLabel}</span>
          <button className="icon-button" onClick={() => setOpenPanel("search")} aria-label="Tìm kiếm sản phẩm">⌕</button>
          <button className="cart-button" onClick={() => setOpenPanel("cart")} aria-label={`Giỏ hàng, ${cartCount} sản phẩm`}>
            <span className="cart-label">Giỏ hàng</span><span className="cart-count">{cartCount}</span>
          </button>
          <button className="menu-button" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen} aria-controls="mobile-navigation" aria-label="Mở menu">
            <i /><i /><i />
          </button>
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
          <div className="hero-proof" aria-label="Tóm tắt phiên gợi ý">
            <div><strong>{products.length}</strong><span>lựa chọn phù hợp</span></div>
            <div><strong>{receipt.latency ? `${receipt.latency}ms` : "Sẵn sàng"}</strong><span>thời gian phản hồi</span></div>
            <div><strong>{personalizationModeLabel}</strong><span>nguồn xếp hạng</span></div>
          </div>
        </div>
        <div className="hero-visual" id="discover" style={{ "--accent": heroProduct.accent } as React.CSSProperties}>
          <div className="hero-orbit orbit-one" /><div className="hero-orbit orbit-two" />
          <div className="visual-label">Chọn riêng cho {profile.firstName}</div>
          <ProductVisual className="hero-product-image" product={heroProduct} />
          <div className="match-badge"><span>Độ phù hợp</span><strong>{Math.round(heroProduct.score * 100)}%</strong></div>
          <div className="hero-product-card">
            <div><span>{heroProduct.category}</span><h2>{heroProduct.name}</h2><p>{displayPrice(heroProduct)}</p></div>
            <button disabled={isAdapting} onClick={() => addToCart(heroProduct)} aria-label={`Thêm ${heroProduct.name} vào giỏ`}>+</button>
          </div>
        </div>
      </section>

      <section className="persona-strip" aria-label="Chọn hồ sơ mua sắm">
        <div className="persona-intro"><span>Xem cá nhân hóa thay đổi</span><strong>Mỗi hồ sơ, một trải nghiệm riêng.</strong></div>
        <div className="persona-options" aria-label="Hồ sơ người dùng">
          {profiles.map((item) => (
            <button
              key={item.id}
              className={item.id === activeId ? "persona active" : "persona"}
              onClick={() => selectProfile(item.id)}
              aria-pressed={item.id === activeId}
              disabled={isLoading && item.id === activeId}
            >
              <span className="avatar">{item.initials}</span>
              <span><strong>{item.label}</strong><small>{item.description}</small></span>
              <i aria-hidden="true" />
            </button>
          ))}
        </div>
      </section>

      <section className="recommendations section-shell" id="recommendations" aria-busy={isLoading}>
        <div className="section-heading">
          <div>
            <div className="eyebrow"><span>02</span> RecoEngine đang chọn</div>
            <h2>Dành riêng cho {profile.firstName}</h2>
            <p>{profile.apiUserId
              ? "Được xếp hạng từ hành vi gần đây, sở thích và ngữ cảnh hiện tại của bạn."
              : "Chưa có lịch sử? Không sao — đây là những lựa chọn đang được yêu thích."}</p>
            <small className="dataset-disclosure">Metadata release đã ẩn danh: mã lựa chọn, nhóm sở thích và phân khúc giá được giữ nguyên từ dataset.</small>
          </div>
          <details className="api-receipt">
            <summary><span className={`pulse ${receipt.degraded ? "degraded" : ""}`} /> {strategyLabel} <span aria-hidden="true">⌄</span></summary>
            <dl>
              <div><dt>Ranker</dt><dd>{receipt.rankerPromoted ? "Đang phục vụ" : "Candidate · chưa promote"}</dd></div>
              <div><dt>Tín hiệu phiên</dt><dd>{receipt.sessionSignalCount}</dd></div>
              <div><dt>Độ trễ</dt><dd>{receipt.latency ? `${receipt.latency} ms` : "—"}</dd></div>
              <div><dt>Mã yêu cầu</dt><dd title={receipt.request ?? undefined}>{receipt.request ?? "Chưa có"}</dd></div>
            </dl>
          </details>
        </div>
        {isLoading && <div className="loading-line" role="status"><span /> Đang cập nhật danh sách cho {profile.label}…</div>}
        {isAdapting && <div className="loading-line adapting" role="status"><span /> Đang dùng tín hiệu mới để xếp hạng lại…</div>}
        {adaptation && !isAdapting && (
          <div className="adaptation-receipt" role="status">
            <div><span>Vòng lặp đã hoàn tất</span><strong>RecoBridge vừa học từ thao tác của bạn</strong></div>
            <p>{adaptation.message}</p>
            <small>{adaptation.signalCount} tín hiệu trong phiên · {adaptation.newProductIds.length} lựa chọn mới</small>
          </div>
        )}
        <div className={`product-grid${isLoading || isAdapting ? " is-loading" : ""}`}>
          {products.map((product, index) => (
            <article className={`product-card${adaptation?.newProductIds.includes(product.id) ? " freshly-ranked" : ""}`} key={`${profile.id}-${product.id}`}>
              <div className="product-image-wrap" style={{ "--card-accent": product.accent } as React.CSSProperties}>
                <span className="rank">{String(index + 1).padStart(2, "0")}</span>
                {adaptation?.newProductIds.includes(product.id) && <span className="fresh-label">Mới theo tín hiệu</span>}
                <button disabled={isAdapting} className={liked.includes(product.id) ? "like active" : "like"} onClick={() => toggleLike(product)} aria-pressed={liked.includes(product.id)} aria-label={liked.includes(product.id) ? `Bỏ lưu ${product.name}` : `Lưu ${product.name}`}>{liked.includes(product.id) ? "♥" : "♡"}</button>
                <ProductVisual className="product-image" product={product} />
                <button disabled={isAdapting} className="quick-add" onClick={() => addToCart(product)}>Thêm vào giỏ <span>+</span></button>
              </div>
              <div className="product-meta">
                <div><span>{product.category}</span><span>{Math.round(product.score * 100)}% phù hợp</span></div>
                <h3>{product.name}</h3><p>{displayPrice(product)}</p><small><i /> {product.reason}</small>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="explain-section" id="how-it-works">
        <div className="explain-card">
          <div className="explain-copy"><div className="eyebrow light"><span>03</span> Minh bạch từ đầu</div><h2>Mỗi gợi ý đều có<br />một lý do.</h2><p>Production hiện dùng baseline theo danh mục và có thể thích nghi trong phiên. XGBRanker vẫn là candidate, chưa tham gia serving cho tới khi vượt promotion gate.</p><a href="#recommendations">Xem lại danh sách của bạn →</a></div>
          <div className="signal-flow" aria-label="Luồng tạo gợi ý"><div className="signal active"><span>01</span><div><strong>Tín hiệu</strong><small>lưu · giỏ hàng · bỏ khỏi giỏ</small></div></div><div className={`connector${adaptation ? " active" : ""}`}><i /></div><div className={`signal${adaptation ? " active" : ""}`}><span>02</span><div><strong>Baseline phiên</strong><small>hồ sơ tạm · re-rank · filter</small></div></div><div className={`connector${adaptation ? " active" : ""}`}><i /></div><div className={`signal${adaptation ? " active" : ""}`}><span>03</span><div><strong>Danh sách mới</strong><small>lý do · thay đổi · truy vết</small></div></div></div>
        </div>
      </section>

      <section className="related section-shell">
        <div className="related-copy"><span className="mini-label">Khám phá thêm</span><h2>Những món đồ<br />hiểu nhau.</h2><p>Gợi ý liên quan theo danh mục, ngữ cảnh và độ tương đồng sản phẩm.</p><button onClick={refreshRelated} disabled={relatedLoading}>{relatedLoading ? "Đang làm mới…" : "Làm mới lựa chọn ↻"}</button></div>
        <div className="related-stage">
          {relatedProducts.map((product, index) => <div className={`related-item item-${index + 1}`} key={`related-${product.id}`}><ProductVisual className="related-image" product={product} /><span>{product.name}</span></div>)}
          <div className="related-center"><span>Sản phẩm gốc</span><strong>{heroProduct.id}</strong></div>
        </div>
      </section>

      <footer>
        <div className="footer-brand"><div className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span>RecoBridge</span></div><p>Kết nối dữ liệu, cá nhân hóa lựa chọn.</p></div>
        <div className="footer-links"><div><span>Sản phẩm</span><a href="#recommendations">Gợi ý</a><a href="#how-it-works">Cách hoạt động</a></div><div><span>Hệ thống</span><a href="#top">API v1</a><a href="#top">Model {receipt.model}</a></div></div>
        <div className="footer-status"><i /> {statusLabel}</div>
      </footer>

      {openPanel && (
        <div className="panel-backdrop" onMouseDown={(event) => event.target === event.currentTarget && setOpenPanel(null)}>
          <section className="side-panel" role="dialog" aria-modal="true" aria-labelledby={`${openPanel}-panel-title`}>
            <div className="panel-heading">
              <div><span>{openPanel === "search" ? "Khám phá" : "Lựa chọn của bạn"}</span><h2 id={`${openPanel}-panel-title`}>{openPanel === "search" ? "Tìm sản phẩm" : `Giỏ hàng (${cartCount})`}</h2></div>
              <button ref={openPanel === "cart" ? closeButton : undefined} onClick={() => setOpenPanel(null)} aria-label="Đóng">×</button>
            </div>
            {openPanel === "search" ? (
              <div className="search-panel-content">
                <label className="search-field"><span className="sr-only">Tên hoặc danh mục sản phẩm</span><span aria-hidden="true">⌕</span><input ref={searchInput} value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Tìm theo tên, danh mục hoặc mã…" /><button onClick={() => setSearchQuery("")} aria-label="Xóa tìm kiếm" disabled={!searchQuery}>×</button></label>
                <p className="result-count">{searchResults.length} kết quả</p>
                <div className="search-results">
                  {searchResults.map((product) => (
                    <div className="search-result" key={`search-${product.id}`}>
                      <ProductVisual className="result-image" product={product} />
                      <div><span>{product.category}</span><strong>{product.name}</strong><small>{displayPrice(product)}</small></div>
                      <button onClick={() => addToCart(product)} aria-label={`Thêm ${product.name} vào giỏ`}>+</button>
                    </div>
                  ))}
                  {!searchResults.length && <div className="empty-state"><strong>Không tìm thấy sản phẩm</strong><p>Thử một tên hoặc danh mục khác.</p></div>}
                </div>
              </div>
            ) : (
              <div className="cart-panel-content">
                <div className="cart-lines">
                  {cartItems.map(({ product, quantity }) => (
                    <div className="cart-line" key={`cart-${product.id}`}>
                      <ProductVisual className="cart-image" product={product} />
                      <div className="cart-line-copy"><span>{product.category}</span><strong>{product.name}</strong><small>{displayPrice(product)}</small></div>
                      <div className="quantity-control"><button onClick={() => updateQuantity(product.id, quantity - 1)} aria-label={`Giảm số lượng ${product.name}`}>−</button><span>{quantity}</span><button onClick={() => updateQuantity(product.id, quantity + 1)} aria-label={`Tăng số lượng ${product.name}`}>+</button></div>
                    </div>
                  ))}
                  {!cartItems.length && <div className="empty-state"><strong>Giỏ hàng đang trống</strong><p>Thêm một sản phẩm phù hợp để bắt đầu.</p><button onClick={() => setOpenPanel(null)}>Tiếp tục khám phá</button></div>}
                </div>
                {!!cartItems.length && <div className="cart-summary"><div><span>Tạm tính</span><strong>{formatPrice(cartTotal)}</strong></div><p>Sản phẩm của bạn được lưu trên thiết bị này.</p><button onClick={() => setOpenPanel(null)}>Tiếp tục khám phá</button><button className="clear-cart" onClick={() => setCart({})}>Xóa giỏ hàng</button></div>}
              </div>
            )}
          </section>
        </div>
      )}

      <div className={toast ? "toast show" : "toast"} role="status" aria-live="polite"><span>✓</span>{toast}</div>
    </main>
  );
}
