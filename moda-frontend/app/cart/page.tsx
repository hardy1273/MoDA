"use client";

// Cart + checkout. Payments run through the backend's provider layer
// (mock provider for now — no real charge happens).

import Link from "next/link";
import { useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { TopBar } from "@/components/TopBar";
import { Order, checkout } from "@/lib/api";
import { useStore } from "@/lib/store";

type Phase = "cart" | "confirm" | "paying" | "done";

export default function Cart() {
  const { session, cart, removeFromCart, setCartQty, clearCart } = useStore();
  const [phase, setPhase] = useState<Phase>("cart");
  const [order, setOrder] = useState<Order | null>(null);
  const [error, setError] = useState<string | null>(null);

  const total = cart.reduce((n, x) => n + x.item.price * x.qty, 0);
  const canCheckout = !!session?.token && cart.every((x) => x.serverId);

  async function pay() {
    setPhase("paying");
    setError(null);
    try {
      const o = await checkout();
      setOrder(o);
      clearCart();
      setPhase("done");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Payment failed — try again.");
      setPhase("confirm");
    }
  }

  if (phase === "done" && order) {
    return (
      <>
        <TopBar />
        <main className="flex-1 px-6 pb-6">
          <div className="mt-12 text-center">
            <p className="text-[26px]">✓</p>
            <h1 className="mt-1 text-[17px] font-bold">Order confirmed</h1>
            <p className="mt-1 text-[12px] text-faint">
              ref {order.payment_ref} · {order.items.length} piece{order.items.length === 1 ? "" : "s"}
            </p>
          </div>
          <ul className="mt-6 divide-y divide-line">
            {order.items.map((it, i) => (
              <li key={i} className="flex items-center gap-4 py-3">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={it.image_url} alt="" className="h-14 w-11 bg-mist object-cover" />
                <div className="min-w-0 flex-1 text-[13px]">
                  <p className="truncate font-medium">{it.name}</p>
                  <p className="text-faint">Size {it.size} · Qty {it.qty}</p>
                </div>
                <span className="text-[13px]">${(it.price * it.qty).toFixed(2)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-center justify-between border-t border-ink pt-3">
            <span className="text-[14px] font-semibold">Paid</span>
            <span className="text-[16px]">${order.total.toFixed(2)}</span>
          </div>
          <div className="mt-8 flex flex-col items-center gap-3 text-[13px]">
            <Link href="/orders" className="underline">View order history</Link>
            <Link href="/feed" className="text-faint underline">Back to your feed</Link>
          </div>
        </main>
        <BottomNav />
      </>
    );
  }

  return (
    <>
      <TopBar />
      <main className="flex-1 px-6 pb-6">
        <h1 className="text-center text-[17px] font-bold lowercase">cart</h1>

        {cart.length === 0 ? (
          <div className="mt-14 text-center text-[14px] text-faint">
            <p>Your cart is empty.</p>
            <Link href="/feed" className="mt-2 inline-block text-ink underline">Browse your feed</Link>
          </div>
        ) : (
          <>
            <ul className="mt-6 divide-y divide-line">
              {cart.map((x) => (
                <li key={`${x.item.id}-${x.size}`} className="flex items-center gap-4 py-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={x.item.image_url} alt="" className="h-20 w-16 bg-mist object-cover" />
                  <div className="min-w-0 flex-1 text-[13px]">
                    <p className="truncate font-medium">{x.item.name}</p>
                    <p className="text-[11px] uppercase tracking-micro text-faint">{x.item.category}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-faint">Size {x.size}</span>
                      <span className="ml-2 inline-flex items-center border border-ink/40">
                        <button
                          aria-label="Decrease quantity"
                          onClick={() =>
                            x.qty > 1
                              ? setCartQty(x.item.id, x.size, x.qty - 1)
                              : removeFromCart(x.item.id, x.size)
                          }
                          className="px-2 py-0.5 hover:bg-mist"
                        >
                          −
                        </button>
                        <span className="min-w-[24px] text-center">{x.qty}</span>
                        <button
                          aria-label="Increase quantity"
                          onClick={() => setCartQty(x.item.id, x.size, Math.min(x.qty + 1, 20))}
                          className="px-2 py-0.5 hover:bg-mist"
                        >
                          +
                        </button>
                      </span>
                    </div>
                    <button
                      onClick={() => removeFromCart(x.item.id, x.size)}
                      className="mt-1 text-faint underline"
                    >
                      Remove
                    </button>
                  </div>
                  <span className="text-[14px]">${(x.item.price * x.qty).toFixed(2)}</span>
                </li>
              ))}
            </ul>

            <div className="mt-4 flex items-center justify-between border-t border-ink pt-4">
              <span className="text-[14px] font-semibold">Total</span>
              <span className="text-[16px]">${total.toFixed(2)}</span>
            </div>

            {error && <p className="mt-3 text-center text-[13px] text-signal">{error}</p>}

            {phase === "cart" &&
              (canCheckout ? (
                <button
                  onClick={() => setPhase("confirm")}
                  className="mt-5 w-full bg-ink py-3 text-[13px] uppercase tracking-micro text-paper hover:bg-ink/85"
                >
                  Checkout
                </button>
              ) : (
                <div className="mt-5 text-center">
                  <Link
                    href="/login"
                    className="block w-full bg-ink py-3 text-[13px] uppercase tracking-micro text-paper hover:bg-ink/85"
                  >
                    Log in to checkout
                  </Link>
                  <p className="mt-2 text-[11px] italic text-faint">
                    Your cart is saved on this device and syncs once you log in.
                  </p>
                </div>
              ))}

            {(phase === "confirm" || phase === "paying") && (
              <div className="mt-5 border border-ink p-4 text-center">
                <p className="text-[13px] font-semibold">MODA Pay</p>
                <p className="mt-1 text-[11px] italic text-faint">
                  test mode — no real charge will be made
                </p>
                <button
                  onClick={pay}
                  disabled={phase === "paying"}
                  className="mt-3 w-full bg-ink py-3 text-[13px] uppercase tracking-micro text-paper hover:bg-ink/85 disabled:opacity-50"
                >
                  {phase === "paying" ? "Processing…" : `Pay $${total.toFixed(2)}`}
                </button>
                <button
                  onClick={() => setPhase("cart")}
                  disabled={phase === "paying"}
                  className="mt-2 text-[12px] text-faint underline disabled:opacity-50"
                >
                  Back
                </button>
              </div>
            )}
          </>
        )}
      </main>
      <BottomNav />
    </>
  );
}
