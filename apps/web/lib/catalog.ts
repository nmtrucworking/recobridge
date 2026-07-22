export type Product = {
  id: string;
  name: string;
  category: string;
  price: number;
  image: string;
  accent: string;
};

export const catalog: Product[] = [
  {
    id: "sku_1048",
    name: "Tai nghe Drift One",
    category: "Âm thanh",
    price: 2490000,
    image: "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=1200&q=88",
    accent: "#d9f34a",
  },
  {
    id: "sku_2091",
    name: "Giày Noma Pace",
    category: "Sneakers",
    price: 1890000,
    image: "https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=1200&q=88",
    accent: "#ff6d48",
  },
  {
    id: "sku_3314",
    name: "Đồng hồ Arc Mini",
    category: "Phụ kiện",
    price: 3290000,
    image: "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=1200&q=88",
    accent: "#9bc8ff",
  },
  {
    id: "sku_4172",
    name: "Kính mát Sora",
    category: "Phụ kiện",
    price: 890000,
    image: "https://images.unsplash.com/photo-1511499767150-a48a237f0083?auto=format&fit=crop&w=1200&q=88",
    accent: "#f6c8dc",
  },
  {
    id: "sku_5088",
    name: "Ghế lounge Lento",
    category: "Nội thất",
    price: 4590000,
    image: "https://images.unsplash.com/photo-1567538096630-e0c55bd6374c?auto=format&fit=crop&w=1200&q=88",
    accent: "#f3c867",
  },
  {
    id: "sku_6270",
    name: "Máy ảnh Miro 35",
    category: "Nhiếp ảnh",
    price: 7890000,
    image: "https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=1200&q=88",
    accent: "#a8b7ff",
  },
  {
    id: "sku_7331",
    name: "Chậu cây Kumo",
    category: "Trang trí",
    price: 690000,
    image: "https://images.unsplash.com/photo-1485955900006-10f4d324d411?auto=format&fit=crop&w=1200&q=88",
    accent: "#b8e5bd",
  },
  {
    id: "sku_8406",
    name: "Balo Field Note",
    category: "Du lịch",
    price: 1590000,
    image: "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=1200&q=88",
    accent: "#f3ad92",
  },
];

export const catalogById = new Map(catalog.map((product) => [product.id, product]));

export const reasonLabels: Record<string, string> = {
  USER_CATEGORY_AFFINITY: "Hợp với sở thích gần đây của bạn",
  CONTEXT_CATEGORY_MATCH: "Phù hợp với danh mục bạn đang xem",
  ITEM_SIMILARITY: "Tương tự sản phẩm bạn quan tâm",
  SAME_CATEGORY: "Cùng danh mục với sản phẩm gốc",
  RECENT_POPULAR: "Phổ biến trong 14 ngày qua",
};
