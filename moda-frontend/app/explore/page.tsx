"use client";

// Explore: the full catalog without personalization filtering.

import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { OutfitCard } from "@/components/OutfitCard";
import { TopBar } from "@/components/TopBar";
import { FeedItem, getFeed } from "@/lib/api";

export default function Explore() {
  const [items, setItems] = useState<FeedItem[] | null>(null);

  useEffect(() => {
    getFeed(24).then((r) => setItems(r.items));
  }, []);

  return (
    <>
      <TopBar />
      <main className="flex-1 px-5 pb-6">
        <h1 className="text-center text-[17px] font-bold lowercase">explore</h1>
        <p className="text-center text-[12px] italic text-faint">everything, beyond your profile</p>
        {items === null ? (
          <div className="mt-6 grid grid-cols-2 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] animate-pulse bg-mist" />
            ))}
          </div>
        ) : (
          <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-6">
            {items.map((it, i) => (
              <OutfitCard key={it.outfit.id} item={it} index={i} />
            ))}
          </div>
        )}
      </main>
      <BottomNav />
    </>
  );
}
