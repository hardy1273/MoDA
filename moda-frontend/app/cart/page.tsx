"use client";

// Cart — commerce stub. Checkout intentionally not wired (MVP scope).

import Link from "next/link";
import { BottomNav } from "@/components/BottomNav";
import { TopBar } from "@/components/TopBar";
import { useStore } from "@/lib/store";

export default function Cart() {
  const { cart, removeFromCart } = useStore();
  const total = cart.reduce((n, x) => n + x.item.price * x.qty, 0);

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
                  <img src={x.item.image_url} alt="" className="h-20 w-16 object-cover bg-mist" />
                  <div className="min-w-0 flex-1 text-[13px]">
                    <p className="truncate font-medium">{x.item.name}</p>
                    <p className="text-[11px] uppercase tracking-micro text-faint">{x.item.category}</p>
                    <p className="text-faint">Size {x.size} · Qty {x.qty}</p>
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
            <button
              disabled
              title="Checkout ships in a later phase"
              className="mt-5 w-full cursor-not-allowed bg-ink/30 py-3 text-[13px] uppercase tracking-micro text-paper"
            >
              Checkout — coming soon
            </button>
          </>
        )}
      </main>
      <BottomNav />
    </>
  );
}
