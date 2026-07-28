import storefront from "./storefront.json";

export type Profile = {
  id: string;
  apiUserId: string | null;
  initials: string;
  label: string;
  firstName: string;
  description: string;
  preferredCategories: string[];
};

export type Product = {
  id: string;
  name: string;
  categoryId: string;
  category: string;
  price: number;
  priceLabel?: string;
  image?: string;
  accent: string;
  popularity: number;
  visualCode?: string;
  metadataSource?: "curated" | "synthetic-presentation";
};

export type RankedProduct = Product & {
  score: number;
  reason: string;
};

export const experience = storefront.experience;
export const categoryLabels: Record<string, string> = storefront.categories;
export const profiles: Profile[] = storefront.profiles;
export const catalog: Product[] = storefront.products.map((product) => ({
  ...product,
  category: categoryLabels[product.categoryId] ?? product.categoryId,
}));
export const catalogById = new Map(catalog.map((product) => [product.id, product]));

export const reasonLabels: Record<string, string> = {
  SESSION_CATEGORY_AFFINITY: "Mới xếp hạng lại từ tín hiệu bạn vừa gửi",
  USER_CATEGORY_AFFINITY: "Hợp với sở thích gần đây của bạn",
  CONTEXT_CATEGORY_MATCH: "Phù hợp với danh mục bạn đang xem",
  ITEM_SIMILARITY: "Tương tự sản phẩm bạn quan tâm",
  SAME_CATEGORY: "Cùng danh mục với sản phẩm gốc",
  RECENT_POPULAR: "Được quan tâm nhiều gần đây",
};

const presentationTemplates = [
  {
    category: "Âm thanh · minh hoạ",
    productLabel: "Tai nghe",
    image: "/products/studio-headphones.png",
    accent: "#d9f34a",
  },
  {
    category: "Chuyển động · minh hoạ",
    productLabel: "Giày",
    image: "/products/studio-sneaker.png",
    accent: "#ff8a66",
  },
  {
    category: "Không gian sống · minh hoạ",
    productLabel: "Ghế",
    image: "/products/studio-lounge.png",
    accent: "#f3c867",
  },
  {
    category: "Hành trình · minh hoạ",
    productLabel: "Bộ hành trình",
    image: "/products/studio-travel.png",
    accent: "#9bc8ff",
  },
] as const;

const presentationNames = [
  "Vela", "Nori", "Drift", "Sora", "Noma", "Luma", "Arco", "Miro",
  "Kumo", "Nara", "Aster", "Nova", "Pico", "Lento", "Halo", "Runa",
] as const;
const presentationEditions = ["One", "Air", "Studio", "Wave", "Flow", "Pace", "Cloud", "Field"] as const;

const stableIndex = (value: string, length: number) => {
  let hash = 2166136261;
  for (const character of value) {
    hash ^= character.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) % length;
};

const presentationTemplateFor = (categoryId: string) =>
  presentationTemplates[stableIndex(categoryId, presentationTemplates.length)];

export const categoryDisplayName = (categoryId?: string | null) => {
  if (!categoryId) return "Nhóm chưa xác định";
  return categoryLabels[categoryId] ?? presentationTemplateFor(categoryId).category;
};

export const priceBucketDisplayName = (priceBucket?: number | null) => {
  if (priceBucket == null) return "Phân khúc đang cập nhật";
  if (priceBucket < 25) return "Phân khúc tiết kiệm";
  if (priceBucket < 50) return "Phân khúc phổ thông";
  if (priceBucket < 75) return "Phân khúc cao cấp";
  return "Phân khúc tuyển chọn";
};

export function hydrateProduct(item: {
  product_id: string;
  category_id?: string | null;
  price_bucket?: number | null;
}): Product {
  const known = catalogById.get(item.product_id);
  if (known) return known;

  const categoryId = item.category_id ?? "other";
  const template = presentationTemplateFor(categoryId);
  const name = presentationNames[stableIndex(item.product_id, presentationNames.length)];
  const edition = presentationEditions[stableIndex(`${item.product_id}:edition`, presentationEditions.length)];
  return {
    id: item.product_id,
    name: `${template.productLabel} ${name} ${edition}`,
    categoryId,
    category: template.category,
    price: 0,
    priceLabel: priceBucketDisplayName(item.price_bucket),
    image: template.image,
    accent: template.accent,
    popularity: 0,
    metadataSource: "synthetic-presentation",
  };
}

export function fallbackProducts(profile: Profile, limit = experience.recommendationLimit): RankedProduct[] {
  return [...catalog]
    .sort((left, right) => {
      const leftPreference = profile.preferredCategories.indexOf(left.categoryId);
      const rightPreference = profile.preferredCategories.indexOf(right.categoryId);
      const leftRank = leftPreference < 0 ? Number.MAX_SAFE_INTEGER : leftPreference;
      const rightRank = rightPreference < 0 ? Number.MAX_SAFE_INTEGER : rightPreference;
      return leftRank - rightRank || right.popularity - left.popularity;
    })
    .slice(0, limit)
    .map((product, index) => ({
      ...product,
      score: Math.max(0.68, 0.9 - index * 0.05),
      reason: profile.preferredCategories.includes(product.categoryId)
        ? "Phù hợp với nhóm sở thích của bạn"
        : "Được quan tâm nhiều gần đây",
    }));
}

export function fallbackRelated(seed: Product, limit = experience.relatedLimit): Product[] {
  return [...catalog]
    .filter((product) => product.id !== seed.id)
    .sort((left, right) => {
      const leftSameCategory = Number(left.categoryId === seed.categoryId);
      const rightSameCategory = Number(right.categoryId === seed.categoryId);
      return rightSameCategory - leftSameCategory || right.popularity - left.popularity;
    })
    .slice(0, limit);
}
