"use client";

import { useMemo, useState } from "react";

type Product = {
  id: string;
  name: string;
  category: string;
  price: number;
  score: number;
  reason: string;
  image: string;
  accent: string;
};

type Profile = {
  id: "mai" | "minh" | "guest";
  short: string;
  label: string;
  taste: string;
  strategy: string;
  model: string;
  latency: number;
  request: string;
  products: Product[];
};

const profiles: Profile[] = [
  {
    id: "mai",
    short: "MA",
    label: "Mai Anh",
    taste: "Công nghệ · Phong cách sống",
    strategy: "hybrid",
    model: "xgb-2026.07.18",
    latency: 47,
    request: "01J-RB-8F2A",
    products: [
      {
        id: "sku_1048",
        name: "Tai nghe Drift One",
        category: "Âm thanh",
        price: 2490000,
        score: 0.94,
        reason: "Hợp gu công nghệ của bạn",
        image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1200&q=88",
        accent: "#d9f34a",
      },
      {
        id: "sku_2091",
        name: "Giày Noma Pace",
        category: "Sneakers",
        price: 1890000,
        score: 0.91,
        reason: "Đang nổi trong nhóm của bạn",
        image: "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1200&q=88",
        accent: "#ff6d48",
      },
      {
        id: "sku_3314",
        name: "Đồng hồ Arc Mini",
        category: "Phụ kiện",
        price: 3290000,
        score: 0.87,
        reason: "Tương tự món bạn đã xem",
        image: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=1200&q=88",
        accent: "#9bc8ff",
      },
      {
        id: "sku_4172",
        name: "Kính mát Sora",
        category: "Phụ kiện",
        price: 890000,
        score: 0.82,
        reason: "Dựa trên sở thích gần đây",
        image: "https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=1200&q=88",
        accent: "#f6c8dc",
      },
    ],
  },
  {
    id: "minh",
    short: "MH",
    label: "Minh Hoàng",
    taste: "Nội thất · Nhiếp ảnh",
    strategy: "hybrid",
    model: "xgb-2026.07.18",
    latency: 53,
    request: "01J-RB-4C7D",
    products: [
      {
        id: "sku_5088",
        name: "Ghế lounge Lento",
        category: "Nội thất",
        price: 4590000,
        score: 0.93,
        reason: "Hợp gu không gian của bạn",
        image: "https://images.unsplash.com/photo-1567538096630-e0c55bd6374c?auto=format&fit=crop&w=1200&q=88",
        accent: "#f3c867",
      },
      {
        id: "sku_6270",
        name: "Máy ảnh Miro 35",
        category: "Nhiếp ảnh",
        price: 7890000,
        score: 0.9,
        reason: "Từ lịch sử khám phá của bạn",
        image: "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=1200&q=88",
        accent: "#a8b7ff",
      },
      {
        id: "sku_7331",
        name: "Chậu cây Kumo",
        category: "Trang trí",
        price: 690000,
        score: 0.85,
        reason: "Phổ biến trong nhóm tương đồng",
        image: "https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=1200&q=88",
        accent: "#b8e5bd",
      },
      {
        id: "sku_8406",
        name: "Balo Field Note",
        category: "Du lịch",
        price: 1590000,
        score: 0.81,
        reason: "Bổ sung cho sở thích nhiếp ảnh",
        image: "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=1200&q=88",
        accent: "#f3ad92",
      },
    ],
  },
  {
    id: "guest",
    short: "AN",
    label: "Khách ẩn danh",
    taste: "Chưa có lịch sử mua sắm",
    strategy: "recent_popular",
    model: "baseline-2026.07.18",
    latency: 21,
    request: "01J-RB-0A9E",
    products: [
      {
        id: "sku_2091",
        name: "Giày Noma Pace",
        category: "Đang thịnh hành",
        price: 1890000,
        score: 0.89,
        reason: "Phổ biến 14 ngày qua",
        image: "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1200&q=88",
        accent: "#ff6d48",
      },
      {
        id: "sku_1048",
        name: "Tai nghe Drift One",
        category: "Bán chạy",
        price: 2490000,
        score: 0.86,
        reason: "Được quan tâm nhiều nhất",
        image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1200&q=88",
        accent: "#d9f34a",
      },
      {
        id: "sku_7331",
        name: "Chậu cây Kumo",
        category: "Nhà cửa",
        price: 690000,
        score: 0.8,
        reason: "Khám phá phổ biến hôm nay",
        image: "https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=1200&q=88",
        accent: "#b8e5bd",
      },
      {
        id: "sku_3314",
        name: "Đồng hồ Arc Mini",
        category: "Phụ kiện",
        price: 3290000,
        score: 0.76,
        reason: "Lựa chọn an toàn cho người mới",
        image: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=1200&q=88",
        accent: "#9bc8ff",
      },
    ],
  },
];

const formatPrice = (price: number) =>
  new Intl.NumberFormat("vi-VN", { style: "currency", currency: "VND" }).format(price);

export default function Home() {
  const [activeId, setActiveId] = useState<Profile["id"]>("mai");
  const [cartCount, setCartCount] = useState(2);
  const [liked, setLiked] = useState<string[]>([]);
  const [toast, setToast] = useState("");

  const profile = useMemo(
    () => profiles.find((item) => item.id === activeId) ?? profiles[0],
    [activeId],
  );
  const heroProduct = profile.products[0];

  const notify = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(""), 2600);
  };

  const selectProfile = (id: Profile["id"]) => {
    setActiveId(id);
    const next = profiles.find((item) => item.id === id);
    if (next) notify(`Đã tải gợi ý cho ${next.label}`);
  };

  const addToCart = (product: Product) => {
    setCartCount((count) => count + 1);
    notify(`Đã thêm ${product.name} · event add_to_cart đã được ghi nhận`);
  };

  const toggleLike = (id: string) => {
    setLiked((items) =>
      items.includes(id) ? items.filter((item) => item !== id) : [...items, id],
    );
  };

  return (
    <main>
      <header className="site-header">
        <a className="brand" href="#top" aria-label="RecoBridge — Trang chủ">
          <span className="brand-mark" aria-hidden="true"><i /><i /><i /></span>
          <span>RecoBridge</span>
        </a>
        <nav className="main-nav" aria-label="Điều hướng chính">
          <a className="active" href="#discover">Khám phá</a>
          <a href="#recommendations">Dành cho bạn</a>
          <a href="#how-it-works">Cách hoạt động</a>
        </nav>
        <div className="header-actions">
          <span className="engine-status"><i /> RecoEngine sẵn sàng</span>
          <button className="icon-button" aria-label="Tìm kiếm">⌕</button>
          <button className="cart-button" aria-label={`Giỏ hàng, ${cartCount} sản phẩm`}>
            Giỏ hàng <span>{cartCount}</span>
          </button>
        </div>
      </header>

      <section className="hero" id="top">
        <div className="hero-copy">
          <div className="eyebrow"><span>01</span> Khám phá theo cách của bạn</div>
          <h1>Gu của bạn,<br /><em>được hiểu đúng.</em></h1>
          <p>
            RecoBridge kết nối từng tín hiệu nhỏ để đưa đúng món đồ đến bạn —
            nhanh, có lý do và không còn những gợi ý vô nghĩa.
          </p>
          <div className="hero-actions">
            <a className="primary-button" href="#recommendations">Xem gợi ý của tôi <span>↗</span></a>
            <a className="text-link" href="#how-it-works">Vì sao tôi thấy những món này? →</a>
          </div>
          <div className="hero-proof">
            <div><strong>200ms</strong><span>mục tiêu p95</span></div>
            <div><strong>Top-N</strong><span>theo ngữ cảnh</span></div>
            <div><strong>24/7</strong><span>fallback an toàn</span></div>
          </div>
        </div>

        <div className="hero-visual" id="discover" style={{ "--accent": heroProduct.accent } as React.CSSProperties}>
          <div className="hero-orbit orbit-one" />
          <div className="hero-orbit orbit-two" />
          <div className="visual-label">Chọn riêng cho {profile.label.split(" ")[0]}</div>
          <div
            className="hero-product-image"
            style={{ backgroundImage: `url(${heroProduct.image})` }}
            role="img"
            aria-label={heroProduct.name}
          />
          <div className="match-badge">
            <span>Độ phù hợp</span>
            <strong>{Math.round(heroProduct.score * 100)}%</strong>
          </div>
          <div className="hero-product-card">
            <div>
              <span>{heroProduct.category}</span>
              <h2>{heroProduct.name}</h2>
              <p>{formatPrice(heroProduct.price)}</p>
            </div>
            <button onClick={() => addToCart(heroProduct)} aria-label={`Thêm ${heroProduct.name} vào giỏ`}>+</button>
          </div>
        </div>
      </section>

      <section className="persona-strip" aria-label="Chọn hồ sơ demo">
        <div className="persona-intro">
          <span>Trải nghiệm trực tiếp</span>
          <strong>Đổi người dùng, đổi cả danh sách.</strong>
        </div>
        <div className="persona-options" role="tablist" aria-label="Hồ sơ người dùng">
          {profiles.map((item) => (
            <button
              key={item.id}
              className={item.id === activeId ? "persona active" : "persona"}
              onClick={() => selectProfile(item.id)}
              role="tab"
              aria-selected={item.id === activeId}
            >
              <span className="avatar">{item.short}</span>
              <span><strong>{item.label}</strong><small>{item.taste}</small></span>
              <i aria-hidden="true" />
            </button>
          ))}
        </div>
      </section>

      <section className="recommendations section-shell" id="recommendations">
        <div className="section-heading">
          <div>
            <div className="eyebrow"><span>02</span> RecoEngine đang chọn</div>
            <h2>Dành riêng cho {profile.label.split(" ").slice(-1)[0]}</h2>
            <p>{profile.id === "guest" ? "Chưa có lịch sử? Không sao — đây là những lựa chọn đang được yêu thích." : "Được xếp hạng từ hành vi gần đây, sở thích và ngữ cảnh hiện tại của bạn."}</p>
          </div>
          <div className="api-receipt" title="Thông tin từ Recommendation API">
            <div><span className="pulse" /> API response</div>
            <dl>
              <div><dt>strategy</dt><dd>{profile.strategy}</dd></div>
              <div><dt>latency</dt><dd>{profile.latency} ms</dd></div>
              <div><dt>request</dt><dd>{profile.request}</dd></div>
            </dl>
          </div>
        </div>

        <div className="product-grid">
          {profile.products.map((product, index) => (
            <article className="product-card" key={`${profile.id}-${product.id}`}>
              <div className="product-image-wrap" style={{ "--card-accent": product.accent } as React.CSSProperties}>
                <span className="rank">0{index + 1}</span>
                <button
                  className={liked.includes(product.id) ? "like active" : "like"}
                  onClick={() => toggleLike(product.id)}
                  aria-label={liked.includes(product.id) ? `Bỏ lưu ${product.name}` : `Lưu ${product.name}`}
                >{liked.includes(product.id) ? "♥" : "♡"}</button>
                <div
                  className="product-image"
                  style={{ backgroundImage: `url(${product.image})` }}
                  role="img"
                  aria-label={product.name}
                />
                <button className="quick-add" onClick={() => addToCart(product)}>Thêm nhanh <span>+</span></button>
              </div>
              <div className="product-meta">
                <div><span>{product.category}</span><span>{Math.round(product.score * 100)}% match</span></div>
                <h3>{product.name}</h3>
                <p>{formatPrice(product.price)}</p>
                <small><i /> {product.reason}</small>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="explain-section" id="how-it-works">
        <div className="explain-card">
          <div className="explain-copy">
            <div className="eyebrow light"><span>03</span> Minh bạch từ đầu</div>
            <h2>Mỗi gợi ý đều có<br />một lý do.</h2>
            <p>
              RecoBridge không chỉ trả về sản phẩm. Mỗi danh sách đi kèm chiến lược,
              phiên bản mô hình và mã lý do để trải nghiệm dễ hiểu, dễ kiểm chứng.
            </p>
            <a href="#recommendations">Xem lại danh sách của bạn →</a>
          </div>
          <div className="signal-flow" aria-label="Luồng tạo gợi ý">
            <div className="signal active"><span>01</span><div><strong>Tín hiệu</strong><small>click · giỏ hàng · mua</small></div></div>
            <div className="connector"><i /></div>
            <div className="signal"><span>02</span><div><strong>RecoEngine</strong><small>candidate · ranking · filter</small></div></div>
            <div className="connector"><i /></div>
            <div className="signal"><span>03</span><div><strong>Gợi ý</strong><small>cá nhân hóa · fallback</small></div></div>
          </div>
        </div>
      </section>

      <section className="related section-shell">
        <div className="related-copy">
          <span className="mini-label">Khám phá thêm</span>
          <h2>Những món đồ<br />hiểu nhau.</h2>
          <p>Gợi ý liên quan theo danh mục, ngữ cảnh và độ tương đồng sản phẩm.</p>
          <button onClick={() => notify("Đã làm mới nhóm sản phẩm liên quan")}>Làm mới lựa chọn ↻</button>
        </div>
        <div className="related-stage">
          {profile.products.slice(1, 4).map((product, index) => (
            <div className={`related-item item-${index + 1}`} key={`related-${product.id}`}>
              <div style={{ backgroundImage: `url(${product.image})` }} role="img" aria-label={product.name} />
              <span>{product.name}</span>
            </div>
          ))}
          <div className="related-center"><span>Seed item</span><strong>{heroProduct.id}</strong></div>
        </div>
      </section>

      <footer>
        <div className="footer-brand">
          <div className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><span>RecoBridge</span></div>
          <p>Kết nối dữ liệu, cá nhân hóa lựa chọn.</p>
        </div>
        <div className="footer-links">
          <div><span>Sản phẩm</span><a href="#recommendations">Gợi ý</a><a href="#how-it-works">Cách hoạt động</a></div>
          <div><span>Hệ thống</span><a href="#top">API v1</a><a href="#top">Model {profile.model}</a></div>
        </div>
        <div className="footer-status"><i /> Hệ thống hoạt động bình thường</div>
      </footer>

      <div className={toast ? "toast show" : "toast"} role="status" aria-live="polite">
        <span>✓</span>{toast}
      </div>
    </main>
  );
}
