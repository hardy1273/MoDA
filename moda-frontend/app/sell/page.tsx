"use client";

// Seller portal: claim a brand, then create and manage listings.
// New and re-photographed listings enter the moderation queue as "pending".

import Link from "next/link";
import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { PayoutsPanel } from "@/components/PayoutsPanel";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import {
  Listing,
  SellerProfile,
  becomeSeller,
  createListing,
  getMyListings,
  getSellerProfile,
  removeListing,
} from "@/lib/api";
import { useStore } from "@/lib/store";

const CATEGORIES = [
  "hoodie", "t-shirt", "shirt", "jacket", "coat", "sweater",
  "jeans", "trousers", "skirt", "dress", "sneakers", "boots", "bag",
];

const inputCls =
  "w-full border border-ink/50 bg-paper px-3 py-2 text-[14px] placeholder:italic placeholder:text-faint focus:border-ink focus:outline-none";

function errorText(e: unknown, fallback: string): string {
  if (!(e instanceof Error)) return fallback;
  if (e.message.startsWith("409")) return "That brand name is already taken.";
  // Backend sends {"detail": "..."} — pull the message out of the raw body
  const m = e.message.match(/"detail":"([^"]+)"/);
  return m ? m[1] : fallback;
}

export default function Sell() {
  const { session } = useStore();
  const [profile, setProfile] = useState<SellerProfile | null | undefined>(undefined);
  const [listings, setListings] = useState<Listing[]>([]);

  const [brand, setBrand] = useState("");
  const [draft, setDraft] = useState({
    name: "", category: "hoodie", image_url: "", price: "", caption: "", tags: "",
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  useEffect(() => {
    if (!session?.token) {
      setProfile(null);
      return;
    }
    getSellerProfile().then((p) => {
      setProfile(p);
      if (p?.is_seller) getMyListings().then(setListings);
    });
  }, [session?.token]);

  async function claimBrand() {
    if (brand.trim().length < 2) {
      setError("Pick a brand name of at least 2 characters.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      setProfile(await becomeSeller(brand.trim()));
      setListings([]);
    } catch (e) {
      setError(errorText(e, "Could not create your seller account."));
    } finally {
      setBusy(false);
    }
  }

  async function submitListing() {
    const price = Number(draft.price);
    if (draft.name.trim().length < 2) return setError("Give your piece a name.");
    if (!draft.image_url.trim().startsWith("http")) return setError("Paste a public image URL (https://…).");
    if (!Number.isFinite(price) || price <= 0) return setError("Enter a price greater than 0.");

    setBusy(true);
    setError(null);
    try {
      const created = await createListing({
        name: draft.name.trim(),
        category: draft.category,
        image_url: draft.image_url.trim(),
        price,
        caption: draft.caption.trim() || undefined,
        style_tags: draft.tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      setListings((l) => [created, ...l]);
      setDraft({ name: "", category: draft.category, image_url: "", price: "", caption: "", tags: "" });
      setFlash("Listing submitted — it goes live once a moderator approves it.");
      setTimeout(() => setFlash(null), 4000);
    } catch (e) {
      setError(errorText(e, "Could not create that listing."));
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setListings((l) => l.filter((x) => x.id !== id));
    await removeListing(id);
  }

  // ---- states ----

  if (profile === undefined) {
    return (
      <>
        <TopBar />
        <main className="flex-1 px-6"><div className="mt-10 h-32 animate-pulse bg-mist" /></main>
        <BottomNav />
      </>
    );
  }

  if (!session?.token || profile === null) {
    return (
      <>
        <TopBar />
        <main className="flex-1 px-6 pb-6">
          <h1 className="text-center text-[17px] font-bold lowercase">sell on moda</h1>
          <p className="mt-14 text-center text-[14px] text-faint">
            <Link href="/login" className="text-ink underline">Log in</Link> to start selling.
          </p>
        </main>
        <BottomNav />
      </>
    );
  }

  if (!profile.is_seller) {
    return (
      <>
        <TopBar />
        <main className="flex-1 px-6 pb-6">
          <h1 className="text-center text-[17px] font-bold lowercase">sell on moda</h1>
          <p className="mt-2 text-center text-[12px] italic text-faint">
            List your pieces and reach shoppers whose taste already matches them.
          </p>
          <div className="mx-auto mt-10 max-w-sm">
            <label className="text-[13px] font-semibold" htmlFor="brand">Your brand name</label>
            <input
              id="brand"
              className={`${inputCls} mt-2`}
              placeholder="e.g. Atelier Nine"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && claimBrand()}
            />
            {error && <p className="mt-2 text-[13px] text-signal">{error}</p>}
            <button
              onClick={claimBrand}
              disabled={busy}
              className="mt-4 w-full bg-ink py-3 text-[13px] uppercase tracking-micro text-paper hover:bg-ink/85 disabled:opacity-50"
            >
              {busy ? "Creating…" : "Become a seller"}
            </button>
            <p className="mt-3 text-center text-[11px] italic text-faint">
              You keep shopping with the same account.
            </p>
          </div>
        </main>
        <BottomNav />
      </>
    );
  }

  return (
    <>
      <TopBar />
      <main className="flex-1 px-6 pb-6">
        <h1 className="text-center text-[17px] font-bold lowercase">seller dashboard</h1>
        <p className="mt-1 text-center text-[12px] italic text-faint">{profile.brand_name}</p>
        {profile.is_admin && (
          <p className="mt-2 text-center text-[12px]">
            <Link href="/admin" className="underline">Review listing queue →</Link>
          </p>
        )}

        <PayoutsPanel />

        <section className="mt-7">
          <h2 className="font-display text-[18px] font-semibold italic">New listing</h2>
          <div className="mt-3 space-y-3">
            <input
              className={inputCls}
              placeholder="Piece name (e.g. Charcoal wool overcoat)"
              value={draft.name}
              onChange={(e) => setDraft({ ...draft, name: e.target.value })}
            />
            <div className="flex gap-3">
              <select
                aria-label="Category"
                className={inputCls}
                value={draft.category}
                onChange={(e) => setDraft({ ...draft, category: e.target.value })}
              >
                {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <input
                className={inputCls}
                inputMode="decimal"
                placeholder="Price (USD)"
                value={draft.price}
                onChange={(e) => setDraft({ ...draft, price: e.target.value })}
              />
            </div>
            <input
              className={inputCls}
              placeholder="Image URL (https://…)"
              value={draft.image_url}
              onChange={(e) => setDraft({ ...draft, image_url: e.target.value })}
            />
            <input
              className={inputCls}
              placeholder="Short description — what it looks like"
              value={draft.caption}
              onChange={(e) => setDraft({ ...draft, caption: e.target.value })}
            />
            <input
              className={inputCls}
              placeholder="Style tags, comma separated (minimal, tailored)"
              value={draft.tags}
              onChange={(e) => setDraft({ ...draft, tags: e.target.value })}
            />

            {error && <p className="text-[13px] text-signal">{error}</p>}
            {flash && <p className="text-[13px]">{flash}</p>}

            <button
              onClick={submitListing}
              disabled={busy}
              className="w-full bg-ink py-3 text-[13px] uppercase tracking-micro text-paper hover:bg-ink/85 disabled:opacity-50"
            >
              {busy ? "Submitting…" : "Submit for review"}
            </button>
            <p className="text-center text-[11px] italic text-faint">
              We read the photo to match your piece to the right shoppers, so use a clear
              shot of the item on its own.
            </p>
          </div>
        </section>

        <section className="mt-9">
          <h2 className="font-display text-[18px] font-semibold italic">
            Your listings {listings.length > 0 && `(${listings.length})`}
          </h2>
          {listings.length === 0 ? (
            <p className="mt-3 text-[13px] text-faint">Nothing listed yet.</p>
          ) : (
            <ul className="mt-3 divide-y divide-line">
              {listings.map((l) => (
                <li key={l.id} className="flex items-start gap-4 py-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={l.image_url} alt="" className="h-20 w-16 bg-mist object-cover" />
                  <div className="min-w-0 flex-1 text-[13px]">
                    <div className="flex items-center gap-2">
                      <p className="truncate font-medium">{l.name}</p>
                      <StatusBadge status={l.status} />
                    </div>
                    <p className="text-[11px] uppercase tracking-micro text-faint">{l.category}</p>
                    {l.review_note && (
                      <p className="mt-1 text-[12px] italic text-signal">
                        Moderator: {l.review_note}
                      </p>
                    )}
                    <button onClick={() => remove(l.id)} className="mt-1 text-faint underline">
                      Remove
                    </button>
                  </div>
                  <span className="text-[14px]">${l.price.toFixed(2)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
      <BottomNav />
    </>
  );
}
