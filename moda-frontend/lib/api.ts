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
  price?: number; // commerce stub — not in backend yet
};

export type FeedItem = { outfit: Outfit; score: number; explanation: string };

export type QuizAnswers = {
  aesthetics: string[];
  colors: string[];
  fits: string[];
  occasions: string[];
  brands: string[];
  inspirations: string[];
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

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json();
}

export type ApiUser = { id: string; email: string; username: string; profile_text: string | null };

// ---------------------------------------------------------------------------
// Public API (each call degrades gracefully to demo mode)
// ---------------------------------------------------------------------------

export async function createUser(username: string, email: string): Promise<ApiUser> {
  try {
    return await http<ApiUser>("/users", {
      method: "POST",
      body: JSON.stringify({ username, email }),
    });
  } catch {
    return { id: "demo-user", email, username, profile_text: null };
  }
}

export async function submitQuiz(userId: string, a: QuizAnswers): Promise<string> {
  const fits = a.layering ? [...a.fits, "layered"] : a.fits;
  try {
    const r = await http<{ profile_text: string }>("/quiz", {
      method: "POST",
      body: JSON.stringify({
        user_id: userId,
        aesthetics: a.aesthetics,
        colors: a.colors,
        fits,
        occasions: a.occasions,
        brands: a.brands,
        inspirations: a.inspirations,
      }),
    });
    return r.profile_text;
  } catch {
    return `A taste profile centered on ${a.aesthetics.join(" and ")} aesthetics; ${fits.join(", ")} silhouettes; ${a.colors.join(", ")} palette.`;
  }
}

export async function getFeed(userId: string, k = 12): Promise<{ items: FeedItem[]; live: boolean }> {
  try {
    const r = await http<{ items: FeedItem[] }>(`/recommendations?user_id=${userId}&k=${k}`);
    return { items: r.items, live: true };
  } catch {
    return { items: demoFeed(k), live: false };
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
  userId: string,
  outfitId: string,
  type: "like" | "dislike" | "save" | "skip",
): Promise<void> {
  if (outfitId.startsWith("demo-")) return;
  try {
    await http("/feedback", {
      method: "POST",
      body: JSON.stringify({ user_id: userId, outfit_id: outfitId, interaction_type: type }),
    });
  } catch {
    /* offline — local state still updates */
  }
}

export async function getSaved(userId: string): Promise<Outfit[] | null> {
  try {
    return await http<Outfit[]>(`/saved?user_id=${userId}`);
  } catch {
    return null; // caller falls back to locally-saved demo items
  }
}
