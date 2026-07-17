"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { TopBar } from "@/components/TopBar";
import { Order, getOrders } from "@/lib/api";
import { useStore } from "@/lib/store";

export default function Orders() {
  const { session } = useStore();
  const [orders, setOrders] = useState<Order[] | null | undefined>(undefined);

  useEffect(() => {
    if (session?.token) getOrders().then(setOrders);
    else setOrders(null);
  }, [session?.token]);

  return (
    <>
      <TopBar />
      <main className="flex-1 px-6 pb-6">
        <h1 className="text-center text-[17px] font-bold lowercase">orders</h1>

        {orders === undefined ? (
          <div className="mt-8 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-20 animate-pulse bg-mist" />
            ))}
          </div>
        ) : orders === null ? (
          <p className="mt-14 text-center text-[14px] text-faint">
            <Link href="/login" className="text-ink underline">Log in</Link> to see your orders.
          </p>
        ) : orders.length === 0 ? (
          <div className="mt-14 text-center text-[14px] text-faint">
            <p>No orders yet.</p>
            <Link href="/feed" className="mt-2 inline-block text-ink underline">Shop your feed</Link>
          </div>
        ) : (
          <ul className="mt-6 space-y-6">
            {orders.map((o) => (
              <li key={o.id} className="border border-line p-4">
                <div className="flex items-baseline justify-between text-[12px]">
                  <span className="font-semibold uppercase tracking-micro">{o.status}</span>
                  <span className="text-faint">
                    {new Date(o.created_at).toLocaleDateString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                </div>
                <div className="mt-3 flex gap-2 overflow-x-auto">
                  {o.items.map((it, i) => (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      key={i}
                      src={it.image_url}
                      alt={it.name}
                      title={`${it.name} ×${it.qty}`}
                      className="h-16 w-12 shrink-0 bg-mist object-cover"
                    />
                  ))}
                </div>
                <div className="mt-3 flex items-baseline justify-between text-[13px]">
                  <span className="text-faint">
                    {o.items.reduce((n, it) => n + it.qty, 0)} pieces · ref {o.payment_ref}
                  </span>
                  <span className="font-semibold">${o.total.toFixed(2)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </main>
      <BottomNav />
    </>
  );
}
