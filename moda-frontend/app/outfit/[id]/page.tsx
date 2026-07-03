"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { TopBar } from "@/components/TopBar";
import { Outfit, getOutfit } from "@/lib/api";
import { useStore } from "@/lib/store";

const SIZES = ["XS", "S", "M", "L", "XL"];

export default function OutfitDetail() {
  const params = useParams<{ id: string }>();
  const { session, liked, saved, toggleLike, toggleSave, addToCart } = useStore();
  const [outfit, setOutfit] = useState<Outfit | null | undefined>(undefined);
  const [size, setSize] = useState("S");
  const [added, setAdded] = useState(false);

  useEffect(() => {
    if (params?.id) getOutfit(params.id).then(setOutfit);
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
  const price = outfit.price ?? 30;
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

        <div className="mt-5 flex items-center gap-3 text-[13px]">
          <span>Sizes:</span>
          {SIZES.map((s) => (
            <button
              key={s}
              onClick={() => setSize(s)}
              aria-pressed={size === s}
              className={`border px-2 py-0.5 ${size === s ? "border-signal text-signal" : "border-ink/50"}`}
            >
              {s}
            </button>
          ))}
          <span className="ml-auto underline">size guide</span>
        </div>

        <div className="mt-4 flex items-center gap-4">
          <button
            onClick={() => {
              addToCart(outfit, size);
              setAdded(true);
              setTimeout(() => setAdded(false), 1600);
            }}
            className="bg-ink px-5 py-2 text-[13px] text-paper hover:bg-ink/85"
          >
            {added ? "Added ✓" : "Add to cart"}
          </button>
          <span className="text-[17px]">${price}</span>
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
