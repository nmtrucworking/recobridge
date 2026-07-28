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
  metadataSource?: "curated" | "anonymized-dataset";
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

const visualPalette = ["#d9f34a", "#ffb38f", "#9bc8ff", "#f6c8dc", "#f3c867", "#a8b7ff", "#b8e5bd"];

const stableIndex = (value: string, length: number) =>
  [...value].reduce((total, character) => total + character.charCodeAt(0), 0) % length;

export const categoryDisplayName = (categoryId?: string | null) => {
  if (!categoryId) return "Nhóm chưa xác định";
  return categoryLabels[categoryId] ?? `Nhóm sở thích #${categoryId}`;
};

export const priceBucketDisplayName = (priceBucket?: number | null) =>
  priceBucket == null ? "Giá đang cập nhật" : `Phân khúc giá #${priceBucket}`;

export function hydrateProduct(item: {
  product_id: string;
  category_id?: string | null;
  price_bucket?: number | null;
}): Product {
  const known = catalogById.get(item.product_id);
  if (known) return known;

  const categoryId = item.category_id ?? "other";
  return {
    id: item.product_id,
    name: `Lựa chọn #${item.product_id.replace(/^sku[_-]?/i, "")}`,
    categoryId,
    category: categoryDisplayName(categoryId),
    price: 0,
    priceLabel: priceBucketDisplayName(item.price_bucket),
    accent: visualPalette[stableIndex(item.product_id, visualPalette.length)],
    popularity: 0,
    visualCode: `#${categoryId}`,
    metadataSource: "anonymized-dataset",
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
