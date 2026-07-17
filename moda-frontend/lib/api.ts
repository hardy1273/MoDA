// MODA API client.
// Talks to the FastAPI backend; if it's unreachable, falls back to a small
// in-memory demo catalog so the UI is fully demoable on its own.

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Outfit = {
  id: string;
  image_url: string;
  caption: string | null;
  style_tags: string[];
  color_tags: string[];
  occasion_tags: string[];
  price?: number; // legacy demo-catalog field; real prices live on items
};

export type Item = {
  id: string;
  name: string;
  category: string;
  image_url: string;
  caption: string | null;
  style_tags: string[];
  color_tags: string[];
  price: number; // dollars (placeholder MVP pricing until sellers set real ones)
};

export type FeedItem = { outfit: Outfit; score: number; explanation: string };

export type QuizAnswers = {
  aesthetics: string[];
  colors: string[];
  fits: string[];
  occasions: string[];
  brands: string[];
  inspirations: string[];
  likedOutfitIds: string[]; // taste-calibration picks
  layering: boolean;
};

// ---------------------------------------------------------------------------
// Demo catalog (used only when the backend is unreachable)
// ---------------------------------------------------------------------------

const demo = (
  id: number,
  url: string,
  caption: string,
  style: string[],
  color: string[],
  occasion: string[],
): Outfit => ({
  id: `demo-${id}`,
  image_url: url,
  caption,
  style_tags: style,
  color_tags: color,
  occasion_tags: occasion,
  price: 24 + ((id * 7) % 56),
});

const u = (q: string) =>
  `https://images.unsplash.com/${q}?auto=format&fit=crop&w=900&q=80`;

export const DEMO_OUTFITS: Outfit[] = [
  demo(1, u("photo-1515886657613-9f3515b0c78f"), "Minimal monochrome look with relaxed tailoring", ["minimal", "modern"], ["black", "white"], ["everyday"]),
  demo(2, u("photo-1490481651871-ab68de25d43d"), "Clean tonal layering with soft neutrals", ["minimal"], ["beige", "cream"], ["everyday"]),
  demo(3, u("photo-1483985988355-763728e1935b"), "Vintage-leaning urban styling", ["vintage", "urban"], ["warm"], ["casual"]),
  demo(4, u("photo-1539109136881-3be0616acf4b"), "Editorial modern silhouette, sharp lines", ["modern"], ["black"], ["nightlife"]),
  demo(5, u("photo-1496747611176-843222e1e57c"), "Relaxed summer set with light layering", ["relaxed", "urban"], ["white", "neutral"], ["travel"]),
  demo(6, u("photo-1485968579580-b6d095142e6e"), "Monochrome streetwear with oversized fit", ["streetwear", "monochrome"], ["grey", "black"], ["everyday"]),
  demo(7, u("photo-1509631179647-0177331693ae"), "Structured vintage tailoring", ["vintage", "tailored"], ["brown"], ["formal"]),
  demo(8, u("photo-1469334031218-e382a71b716b"), "Airy modern look with statement layering", ["modern", "layered"], ["pastel"], ["everyday"]),
];

const demoFeed = (k: number): FeedItem[] =>
  DEMO_OUTFITS.slice(0, k).map((o, i) => ({
    outfit: o,
    score: 0.92 - i * 0.04,
    explanation:
      o.style_tags.length >= 2
        ? `Recommended because you like ${o.style_tags[0]} and ${o.style_tags[1]} pieces.`
        : `Recommended because you like ${o.style_tags[0]} styles.`,
  }));

// ---------------------------------------------------------------------------
// HTTP helpers
// ---------------------------------------------------------------------------

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem("moda.session");
    const token = raw ? (JSON.parse(raw)?.token as string | null) : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeaders(), ...init?.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

// fetch() rejects with TypeError when the backend is unreachable; HTTP
// errors (409 email taken, 401 bad password, …) arrive as Error above.
// Demo fallback should only kick in for the former.
const isNetworkError = (e: unknown) => e instanceof TypeError;

export type ApiUser = { id: string; email: string; username: string; profile_text: string | null };
export type AuthResult = { user: ApiUser; token: string | null };

// ---------------------------------------------------------------------------
// Public API (each call degrades gracefully to demo mode)
// ---------------------------------------------------------------------------

export async function signup(username: string, email: string, password: string): Promise<AuthResult> {
  try {
    const r = await http<{ access_token: string; user: ApiUser }>("/auth/signup", {
      method: "POST",
      body: JSON.stringify({ username, email, password }),
    });
    return { user: r.user, token: r.access_token };
  } catch (e) {
    if (isNetworkError(e)) {
      return { user: { id: "demo-user", email, username, profile_text: null }, token: null };
    }
    throw e; // e.g. 409 email/username taken — let the form show it
  }
}

export async function login(email: string, password: string): Promise<AuthResult> {
  const r = await http<{ access_token: string; user: ApiUser }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  return { user: r.user, token: r.access_token };
}

export async function submitQuiz(a: QuizAnswers): Promise<string> {
  const fits = a.layering ? [...a.fits, "layered"] : a.fits;
  try {
    const r = await http<{ profile_text: string }>("/quiz", {
      method: "POST",
      body: JSON.stringify({
        aesthetics: a.aesthetics,
        colors: a.colors,
        fits,
        occasions: a.occasions,
        brands: a.brands,
        inspirations: a.inspirations,
        liked_outfit_ids: a.likedOutfitIds.filter((id) => !id.startsWith("demo-")),
      }),
    });
    return r.profile_text;
  } catch {
    return `A taste profile centered on ${a.aesthetics.join(" and ")} aesthetics; ${fits.join(", ")} silhouettes; ${a.colors.join(", ")} palette.`;
  }
}

export async function getFeed(k = 12): Promise<{ items: FeedItem[]; live: boolean }> {
  try {
    const r = await http<{ items: FeedItem[] }>(`/recommendations?k=${k}`);
    return { items: r.items, live: true };
  } catch {
    return { items: demoFeed(k), live: false };
  }
}

export async function getSampleOutfits(n = 12): Promise<Outfit[]> {
  try {
    return await http<Outfit[]>(`/outfits/sample?n=${n}`);
  } catch {
    return DEMO_OUTFITS.slice(0, n);
  }
}

export async function getOutfitItems(outfitId: string): Promise<Item[]> {
  if (outfitId.startsWith("demo-")) return [];
  try {
    return await http<Item[]>(`/outfits/${outfitId}/items`);
  } catch {
    return [];
  }
}

/** Personalized item feed; falls back to the unpersonalized catalog, then []. */
export async function getItems(k = 24): Promise<Item[]> {
  try {
    return await http<Item[]>(`/items/recommended?k=${k}`);
  } catch {
    try {
      return await http<Item[]>(`/items?k=${k}`);
    } catch {
      return [];
    }
  }
}

export async function getOutfit(id: string): Promise<Outfit | null> {
  if (id.startsWith("demo-")) return DEMO_OUTFITS.find((o) => o.id === id) ?? null;
  try {
    return await http<Outfit>(`/outfits/${id}`);
  } catch {
    return null;
  }
}

export async function sendFeedback(
  outfitId: string,
  type: "like" | "dislike" | "save" | "skip",
): Promise<void> {
  if (outfitId.startsWith("demo-")) return;
  try {
    await http("/feedback", {
      method: "POST",
      body: JSON.stringify({ outfit_id: outfitId, interaction_type: type }),
    });
  } catch {
    /* offline or logged out — local state still updates */
  }
}

export async function getSaved(): Promise<Outfit[] | null> {
  try {
    return await http<Outfit[]>("/saved");
  } catch {
    return null; // caller falls back to locally-saved demo items
  }
}

// ---------------------------------------------------------------------------
// Cart & orders (server-side for logged-in users; store falls back to local)
// ---------------------------------------------------------------------------

export type CartLine = { id: string; item: Item; size: string; qty: number };
export type CartData = { items: CartLine[]; total: number };

export type OrderLine = {
  name: string;
  image_url: string;
  price: number;
  size: string;
  qty: number;
};

export type Order = {
  id: string;
  status: string;
  total: number;
  payment_provider: string;
  payment_ref: string;
  created_at: string;
  items: OrderLine[];
};

/** All cart calls return null when offline or logged out — the store then
 *  keeps its localStorage-only behavior. */
export async function getCart(): Promise<CartData | null> {
  try {
    return await http<CartData>("/cart");
  } catch {
    return null;
  }
}

export async function addCartLine(itemId: string, size: string, qty = 1): Promise<CartData | null> {
  try {
    return await http<CartData>("/cart/items", {
      method: "POST",
      body: JSON.stringify({ item_id: itemId, size, qty }),
    });
  } catch {
    return null;
  }
}

export async function updateCartLine(lineId: string, qty: number): Promise<CartData | null> {
  try {
    return await http<CartData>(`/cart/items/${lineId}`, {
      method: "PATCH",
      body: JSON.stringify({ qty }),
    });
  } catch {
    return null;
  }
}

export async function removeCartLine(lineId: string): Promise<CartData | null> {
  try {
    return await http<CartData>(`/cart/items/${lineId}`, { method: "DELETE" });
  } catch {
    return null;
  }
}

/** Throws on failure so the cart page can show what went wrong. */
export async function checkout(): Promise<Order> {
  return http<Order>("/checkout", { method: "POST" });
}

export async function getOrders(): Promise<Order[] | null> {
  try {
    return await http<Order[]>("/orders");
  } catch {
    return null;
  }
}
