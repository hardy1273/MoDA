"use client";

import Link from "next/link";
import { FeedItem } from "@/lib/api";
import { useStore } from "@/lib/store";

export function OutfitCard({ item, index }: { item: FeedItem; index: number }) {
  const { liked, saved, toggleLike, toggleSave, addToCart } = useStore();
  const o = item.outfit;
  const isLiked = !!liked[o.id];
  const isSaved = !!saved[o.id];
  const price = o.price ?? 30;

  return (
    <article className="flex flex-col">
      <Link href={`/outfit/${o.id}`} className="group relative block overflow-hidden bg-mist">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={o.image_url}
          alt={o.caption ?? "Outfit"}
          className="aspect-[3/4] w-full object-cover transition-transform duration-500 group-hover:scale-[1.03]"
          loading={index < 4 ? "eager" : "lazy"}
        />
      </Link>

      <div className="mt-2 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <Link href={`/outfit/${o.id}`} className="block truncate text-[13px] font-medium">
            {o.style_tags[0] ? `${o.style_tags[0]} look` : "Look"} #{index + 1}
          </Link>
          <span className="text-[13px] text-faint">${price}</span>
        </div>
        <div className="flex items-center gap-2 pt-0.5">
          <button
            aria-label={isLiked ? "Unlike" : "Like"}
            aria-pressed={isLiked}
            onClick={() => toggleLike(o)}
            className={isLiked ? "text-signal" : "text-ink/60 hover:text-ink"}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill={isLiked ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.5">
              <path d="M12 21s-7.5-4.7-9.7-9A5.4 5.4 0 0 1 12 6.6 5.4 5.4 0 0 1 21.7 12c-2.2 4.3-9.7 9-9.7 9Z" />
            </svg>
          </button>
          <button
            aria-label={isSaved ? "Remove from closet" : "Save to closet"}
            aria-pressed={isSaved}
            onClick={() => toggleSave(o)}
            className="text-ink/60 hover:text-ink"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill={isSaved ? "currentColor" : "none"} stroke="currentColor" strokeWidth="1.5">
              <path d="M6 3h12v18l-6-4.5L6 21V3Z" />
            </svg>
          </button>
        </div>
      </div>

      <button
        onClick={() => addToCart(o, "M")}
        className="mt-1.5 self-start border border-ink px-2.5 py-1 text-[11px] tracking-micro uppercase hover:bg-ink hover:text-paper"
      >
        Add to cart
      </button>
    </article>
  );
}
