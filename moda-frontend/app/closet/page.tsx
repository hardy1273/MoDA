"use client";

// Closet = saved outfits. Prefers backend /saved; falls back to local saves.

import Link from "next/link";
import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { TopBar } from "@/components/TopBar";
import { Outfit, getSaved } from "@/lib/api";
import { useStore } from "@/lib/store";

export default function Closet() {
  const { session, saved, toggleSave } = useStore();
  const [remote, setRemote] = useState<Outfit[] | null>(null);

  useEffect(() => {
    if (session?.userId && session.userId !== "demo-user") {
      getSaved(session.userId).then(setRemote);
    }
  }, [session?.userId]);

  const local = Object.values(saved);
  const merged = new Map<string, Outfit>();
  (remote ?? []).forEach((o) => merged.set(o.id, o));
  local.forEach((o) => merged.set(o.id, o));
  const items = Array.from(merged.values());

  return (
    <>
      <TopBar />
      <main className="flex-1 px-5 pb-6">
        <h1 className="text-center text-[17px] font-bold lowercase">your closet</h1>
        <p className="text-center text-[12px] italic text-faint">pieces you saved</p>

        {items.length === 0 ? (
          <div className="mt-14 text-center text-[14px] text-faint">
            <p>Your closet is empty.</p>
            <Link href="/feed" className="mt-2 inline-block text-ink underline">
              Save pieces from your feed
            </Link>
          </div>
        ) : (
          <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-6">
            {items.map((o) => (
              <article key={o.id} className="flex flex-col">
                <Link href={`/outfit/${o.id}`} className="block overflow-hidden bg-mist">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={o.image_url} alt={o.caption ?? "Saved outfit"} className="aspect-[3/4] w-full object-cover" />
                </Link>
                <div className="mt-2 flex items-center justify-between text-[13px]">
                  <span className="truncate font-medium">{o.style_tags[0] ?? "saved"} look</span>
                  <button onClick={() => toggleSave(o)} className="text-faint underline">remove</button>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
      <BottomNav />
    </>
  );
}
