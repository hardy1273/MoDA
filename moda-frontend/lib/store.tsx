"use client";

// Session + cart + reactions store.
// Persisted to localStorage so refreshes keep state; like/save also fire
// feedback calls to the backend so the taste vector actually moves.

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import { Outfit, sendFeedback } from "./api";

type Session = {
  userId: string;
  username: string;
  profileText: string | null;
  token: string | null; // null = demo mode (backend unreachable at signup)
};
type CartItem = { outfit: Outfit; size: string; qty: number };

type Store = {
  session: Session | null;
  setSession: (s: Session | null) => void;
  setProfileText: (t: string) => void;

  cart: CartItem[];
  addToCart: (outfit: Outfit, size: string) => void;
  removeFromCart: (outfitId: string, size: string) => void;
  cartCount: number;

  liked: Record<string, Outfit>;
  saved: Record<string, Outfit>;
  toggleLike: (o: Outfit) => void;
  toggleSave: (o: Outfit) => void;
  dismiss: (o: Outfit) => void;
};

const Ctx = createContext<Store | null>(null);

function load<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [liked, setLiked] = useState<Record<string, Outfit>>({});
  const [saved, setSaved] = useState<Record<string, Outfit>>({});
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setSession(load("moda.session", null));
    setCart(load("moda.cart", []));
    setLiked(load("moda.liked", {}));
    setSaved(load("moda.saved", {}));
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    localStorage.setItem("moda.session", JSON.stringify(session));
    localStorage.setItem("moda.cart", JSON.stringify(cart));
    localStorage.setItem("moda.liked", JSON.stringify(liked));
    localStorage.setItem("moda.saved", JSON.stringify(saved));
  }, [session, cart, liked, saved, hydrated]);

  const value = useMemo<Store>(() => {
    const uid = session?.userId;
    return {
      session,
      setSession,
      setProfileText: (t) => setSession((s) => (s ? { ...s, profileText: t } : s)),

      cart,
      addToCart: (outfit, size) =>
        setCart((c) => {
          const i = c.findIndex((x) => x.outfit.id === outfit.id && x.size === size);
          if (i >= 0) {
            const next = [...c];
            next[i] = { ...next[i], qty: next[i].qty + 1 };
            return next;
          }
          return [...c, { outfit, size, qty: 1 }];
        }),
      removeFromCart: (outfitId, size) =>
        setCart((c) => c.filter((x) => !(x.outfit.id === outfitId && x.size === size))),
      cartCount: cart.reduce((n, x) => n + x.qty, 0),

      liked,
      saved,
      toggleLike: (o) =>
        setLiked((m) => {
          const next = { ...m };
          if (next[o.id]) delete next[o.id];
          else {
            next[o.id] = o;
            if (uid) void sendFeedback(o.id, "like");
          }
          return next;
        }),
      toggleSave: (o) =>
        setSaved((m) => {
          const next = { ...m };
          if (next[o.id]) delete next[o.id];
          else {
            next[o.id] = o;
            if (uid) void sendFeedback(o.id, "save");
          }
          return next;
        }),
      dismiss: (o) => {
        if (uid) void sendFeedback(o.id, "dislike");
      },
    };
  }, [session, cart, liked, saved]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useStore(): Store {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useStore must be used inside <StoreProvider>");
  return ctx;
}
