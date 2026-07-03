"use client";

import { useEffect, useMemo, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { OutfitCard } from "@/components/OutfitCard";
import { TopBar } from "@/components/TopBar";
import { FeedItem, getFeed } from "@/lib/api";
import { useStore } from "@/lib/store";

const THEMES = ["all", "vintage", "modern", "minimal", "streetwear", "urban"];

export default function Feed() {
  const { session } = useStore();
  const [items, setItems] = useState<FeedItem[] | null>(null);
  const [live, setLive] = useState(true);
  const [theme, setTheme] = useState("all");

  useEffect(() => {
    let cancelled = false;
    getFeed(12).then((r) => {
      if (cancelled) return;
      setItems(r.items);
      setLive(r.live);
    });
    return () => {
      cancelled = true;
    };
  }, [session?.userId]);

  const visible = useMemo(() => {
    if (!items) return null;
    if (theme === "all") return items;
    return items.filter((it) =>
      [...it.outfit.style_tags, ...it.outfit.occasion_tags].some((t) =>
        t.toLowerCase().includes(theme),
      ),
    );
  }, [items, theme]);

  const suggested = items?.[0]?.outfit.style_tags[0] ?? "minimal";

  return (
    <>
      <TopBar />
      <main className="flex-1 px-5 pb-6">
        <div className="text-center">
          <h1 className="text-[17px] font-bold lowercase">recommended for you</h1>
          <p className="text-[12px] italic text-faint">Suggested theme: {suggested}</p>
        </div>

        <div className="mt-4 flex items-center gap-2 overflow-x-auto pb-1 text-[12px]">
          <span className="shrink-0 text-faint">More themes:</span>
          {THEMES.map((t) => (
            <button
              key={t}
              onClick={() => setTheme(t)}
              aria-pressed={theme === t}
              className={`shrink-0 border px-2.5 py-1 ${
                theme === t ? "border-ink bg-ink text-paper" : "border-ink/50 hover:bg-mist"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {!live && (
          <p className="mt-3 border border-line bg-mist px-3 py-2 text-[12px] text-faint">
            Demo catalog — start the MODA backend to see live personalized recommendations.
          </p>
        )}

        {visible === null ? (
          <div className="mt-6 grid grid-cols-2 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="aspect-[3/4] animate-pulse bg-mist" />
            ))}
          </div>
        ) : visible.length === 0 ? (
          <p className="mt-10 text-center text-[14px] text-faint">
            Nothing in this theme yet. Try another, or like a few pieces to teach MODA your taste.
          </p>
        ) : (
          <div className="mt-5 grid grid-cols-2 gap-x-4 gap-y-6">
            {visible.map((it, i) => (
              <OutfitCard key={it.outfit.id} item={it} index={i} />
            ))}
          </div>
        )}
      </main>
      <BottomNav />
    </>
  );
}
