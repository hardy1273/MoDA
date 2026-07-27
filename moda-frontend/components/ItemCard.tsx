"use client";

import { useState } from "react";
import { Item } from "@/lib/api";
import { useStore } from "@/lib/store";

const SIZES = ["XS", "S", "M", "L", "XL"];
// Shoes use numeric sizing; bags are one-size
const SHOE_SIZES = ["7", "8", "9", "10", "11", "12"];
const ONE_SIZE = ["One size"];

function sizesFor(category: string): string[] {
  if (category === "sneakers" || category === "boots") return SHOE_SIZES;
  if (category === "bag") return ONE_SIZE;
  return SIZES;
}

export function ItemCard({ item }: { item: Item }) {
  const { addToCart } = useStore();
  const sizes = sizesFor(item.category);
  const [size, setSize] = useState(sizes[Math.floor(sizes.length / 2) - (sizes.length > 1 ? 1 : 0)] ?? sizes[0]);
  const [added, setAdded] = useState(false);

  return (
    <article className="flex flex-col">
      <div className="overflow-hidden bg-mist">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={item.image_url} alt={item.name} className="aspect-square w-full object-cover" />
      </div>
      <div className="mt-2 flex items-baseline justify-between gap-2 text-[13px]">
        <span className="truncate font-medium">{item.name}</span>
        <span className="shrink-0">${item.price.toFixed(2)}</span>
      </div>
      <p className="text-[11px] uppercase tracking-micro text-faint">
        {item.brand_name ? `${item.category} · ${item.brand_name}` : item.category}
      </p>
      <div className="mt-1.5 flex items-center gap-1.5">
        <select
          value={size}
          onChange={(e) => setSize(e.target.value)}
          aria-label={`Size for ${item.name}`}
          className="min-w-0 flex-1 border border-ink/40 bg-paper px-1.5 py-1 text-[12px]"
        >
          {sizes.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <button
          onClick={() => {
            addToCart(item, size);
            setAdded(true);
            setTimeout(() => setAdded(false), 1400);
          }}
          className="shrink-0 bg-ink px-2.5 py-1 text-[12px] text-paper hover:bg-ink/85"
        >
          {added ? "✓" : "Add"}
        </button>
      </div>
    </article>
  );
}
