"use client";

// Explore: looks (full outfit catalog) and pieces (individual items).

import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { ItemCard } from "@/components/ItemCard";
import { OutfitCard } from "@/components/OutfitCard";
import { TopBar } from "@/components/TopBar";
import { FeedItem, Item, getFeed, getItems } from "@/lib/api";

export default function Explore() {
  const [tab, setTab] = useState<"looks" | "pieces">("looks");
  const [looks, setLooks] = useState<FeedItem[] | null>(null);
  const [pieces, setPieces] = useState<Item[] | null>(null);

  useEffect(() => {
    getFeed(24).then((r) => setLooks(r.items));
    getItems(24).then(setPieces);
  }, []);

  const skeleton = (
    <div className="mt-6 grid grid-cols-2 gap-4">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="aspect-[3/4] animate-pulse bg-mist" />
      ))}
    </div>
  );

  return (
    <>
      <TopBar />
      <main className="flex-1 px-5 pb-6">
        <h1 className="text-center text-[17px] font-bold lowercase">explore</h1>
        <p className="text-center text-[12px] italic text-faint">everything, beyond your profile</p>

        <div className="mt-4 flex justify-center gap-2 text-[12px]">
          {(["looks", "pieces"] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              aria-pressed={tab === t}
              className={`border px-4 py-1 ${
                tab === t ? "border-ink bg-ink text-paper" : "border-ink/50 hover:bg-mist"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {tab === "looks" ? (
          looks === null ? (
            skeleton
          ) : (
            <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-6">
              {looks.map((it, i) => (
                <OutfitCard key={it.outfit.id} item={it} index={i} />
              ))}
            </div>
          )
        ) : pieces === null ? (
          skeleton
        ) : pieces.length === 0 ? (
          <p className="mt-10 text-center text-[14px] text-faint">
            No pieces in the catalog yet — start the backend and ingest items.
          </p>
        ) : (
          <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-6">
            {pieces.map((it) => (
              <ItemCard key={it.id} item={it} />
            ))}
          </div>
        )}
      </main>
      <BottomNav />
    </>
  );
}
