"use client";

// Session + cart + reactions store.
// Persisted to localStorage so refreshes keep state; like/save also fire
// feedback calls to the backend so the taste vector actually moves.

import React, { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  CartData,
  Item,
  Outfit,
  addCartLine,
  getCart,
  removeCartLine,
  sendFeedback,
  updateCartLine,
} from "./api";

type Session = {
  userId: string;
  username: string;
  profileText: string | null;
  token: string | null; // null = demo mode (backend unreachable at signup)
};
// serverId is set when the line is mirrored in the backend cart
type CartItem = { item: Item; size: string; qty: number; serverId?: string };

type Store = {
  session: Session | null;
  setSession: (s: Session | null) => void;
  setProfileText: (t: string) => void;

  cart: CartItem[];
  addToCart: (item: Item, size: string) => void;
  removeFromCart: (itemId: string, size: string) => void;
  setCartQty: (itemId: string, size: string, qty: number) => void;
  clearCart: () => void;
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

function fromServer(c: CartData): CartItem[] {
  return c.items.map((l) => ({ item: l.item, size: l.size, qty: l.qty, serverId: l.id }));
}

export function StoreProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [cart, setCart] = useState<CartItem[]>([]);
  const [liked, setLiked] = useState<Record<string, Outfit>>({});
  const [saved, setSaved] = useState<Record<string, Outfit>>({});
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setSession(load("moda.session", null));
    // Drop cart entries from the pre-items era (they held outfits, not items)
    setCart(load<CartItem[]>("moda.cart", []).filter((x) => x?.item?.id));
    setLiked(load("moda.liked", {}));
    setSaved(load("moda.saved", {}));
    setHydrated(true);
  }, []);

  // Logged in: the server cart is the source of truth. Lines added while
  // logged out (no serverId) are pushed up first so nothing is lost.
  const token = session?.token;
  useEffect(() => {
    if (!hydrated || !token) return;
    (async () => {
      const locals = cart.filter((x) => !x.serverId && !x.item.id.startsWith("demo-"));
      for (const l of locals) await addCartLine(l.item.id, l.size, l.qty);
      const c = await getCart();
      if (c) setCart(fromServer(c));
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- sync runs on login only
  }, [hydrated, token]);

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
      addToCart: (item, size) => {
        // Optimistic local update; server response (with line ids) reconciles
        setCart((c) => {
          const i = c.findIndex((x) => x.item.id === item.id && x.size === size);
          if (i >= 0) {
            const next = [...c];
            next[i] = { ...next[i], qty: next[i].qty + 1 };
            return next;
          }
          return [...c, { item, size, qty: 1 }];
        });
        if (session?.token && !item.id.startsWith("demo-")) {
          void addCartLine(item.id, size).then((r) => r && setCart(fromServer(r)));
        }
      },
      removeFromCart: (itemId, size) => {
        const line = cart.find((x) => x.item.id === itemId && x.size === size);
        setCart((c) => c.filter((x) => !(x.item.id === itemId && x.size === size)));
        if (line?.serverId) {
          void removeCartLine(line.serverId).then((r) => r && setCart(fromServer(r)));
        }
      },
      setCartQty: (itemId, size, qty) => {
        if (qty <= 0) return; // removal goes through removeFromCart
        const line = cart.find((x) => x.item.id === itemId && x.size === size);
        setCart((c) =>
          c.map((x) => (x.item.id === itemId && x.size === size ? { ...x, qty } : x)),
        );
        if (line?.serverId) {
          void updateCartLine(line.serverId, qty).then((r) => r && setCart(fromServer(r)));
        }
      },
      clearCart: () => setCart([]),
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
