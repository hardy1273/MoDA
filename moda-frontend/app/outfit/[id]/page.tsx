"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { ItemCard } from "@/components/ItemCard";
import { TopBar } from "@/components/TopBar";
import { Item, Outfit, getOutfit, getOutfitItems } from "@/lib/api";
import { useStore } from "@/lib/store";

export default function OutfitDetail() {
  const params = useParams<{ id: string }>();
  const { session, liked, saved, toggleLike, toggleSave } = useStore();
  const [outfit, setOutfit] = useState<Outfit | null | undefined>(undefined);
  const [items, setItems] = useState<Item[] | null>(null);

  useEffect(() => {
    if (params?.id) {
      getOutfit(params.id).then(setOutfit);
      getOutfitItems(params.id).then(setItems);
    }
  }, [params?.id]);

  if (outfit === undefined) {
    return (
      <>
        <TopBar />
        <main className="flex-1 px-6"><div className="mt-8 aspect-[3/4] animate-pulse bg-mist" /></main>
        <BottomNav />
      </>
    );
  }

  if (outfit === null) {
    return (
      <>
        <TopBar />
        <main className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="text-[14px]">This piece isn&apos;t available.</p>
          <Link href="/feed" className="text-[13px] underline">Back to your feed</Link>
        </main>
        <BottomNav />
      </>
    );
  }

  const isLiked = !!liked[outfit.id];
  const isSaved = !!saved[outfit.id];
  const lookTotal = items?.reduce((n, it) => n + it.price, 0) ?? 0;
  const theme = outfit.style_tags[0] ?? "minimal";
  const profileHint = session?.profileText
    ? session.profileText.replace(/^A taste profile centered on /i, "").replace(/\.$/, "")
    : "your style profile";

  return (
    <>
      <TopBar />
      <main className="flex-1 px-6 pb-8">
        <Link href="/feed" className="text-[13px] font-semibold italic">← feed</Link>

        <h1 className="mt-2 text-center text-[20px] font-semibold capitalize">{theme} look</h1>
        <p className="text-center text-[12px] italic text-faint">theme : {theme}</p>

        <div className="mt-4 bg-mist">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={outfit.image_url} alt={outfit.caption ?? "Outfit"} className="aspect-[3/4] w-full object-cover" />
        </div>

        <div className="mt-4 flex items-center gap-4">
          <div className="ml-auto flex items-center gap-3">
            <button
              aria-label={isLiked ? "Unlike" : "Like"}
              onClick={() => toggleLike(outfit)}
              className={isLiked ? "text-signal" : "text-ink/60 hover:text-ink"}
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill={isLiked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.5">
                <path d="M12 21s-7.5-4.7-9.7-9A5.4 5.4 0 0 1 12 6.6 5.4 5.4 0 0 1 21.7 12c-2.2 4.3-9.7 9-9.7 9Z" />
              </svg>
            </button>
            <button
              aria-label={isSaved ? "Remove from closet" : "Save to closet"}
              onClick={() => toggleSave(outfit)}
              className="text-ink/60 hover:text-ink"
            >
              <svg width="22" height="22" viewBox="0 0 24 24" fill={isSaved ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.5">
                <path d="M6 3h12v18l-6-4.5L6 21V3Z" />
              </svg>
            </button>
          </div>
        </div>

        <section className="mt-6">
          <h2 className="text-center font-display text-[18px] font-semibold italic">Shop this look</h2>
          {items === null ? (
            <div className="mt-3 grid grid-cols-2 gap-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="aspect-square animate-pulse bg-mist" />
              ))}
            </div>
          ) : items.length === 0 ? (
            <p className="mt-2 text-center text-[12px] italic text-faint">
              No matching pieces yet — check back soon.
            </p>
          ) : (
            <>
              <p className="mt-1 text-center text-[11px] italic text-faint">
                similar pieces, matched to this look · get it all for ${lookTotal.toFixed(2)}
              </p>
              <div className="mt-3 grid grid-cols-2 gap-4">
                {items.map((it) => (
                  <ItemCard key={it.id} item={it} />
                ))}
              </div>
            </>
          )}
        </section>

        <section className="mt-7 text-center">
          <h2 className="font-display text-[18px] font-semibold italic">Why this design?</h2>
          <p className="mx-auto mt-2 max-w-[300px] text-[12px] italic leading-relaxed text-ink/75">
            {outfit.caption
              ? `${outfit.caption}. Picked because it aligns with ${profileHint}.`
              : `Picked because it aligns with ${profileHint}.`}
          </p>
          {outfit.style_tags.length > 0 && (
            <p className="mt-3 text-[11px] uppercase tracking-micro text-faint">
              {[...outfit.style_tags, ...outfit.color_tags].slice(0, 5).join(" · ")}
            </p>
          )}
        </section>
      </main>
      <BottomNav />
    </>
  );
}
