"use client";

// Moderation queue. Visible only to accounts with is_admin
// (granted via `python -m scripts.grant_admin --email ...`).

import Link from "next/link";
import { useEffect, useState } from "react";
import { BottomNav } from "@/components/BottomNav";
import { StatusBadge } from "@/components/StatusBadge";
import { TopBar } from "@/components/TopBar";
import {
  Listing,
  ListingStatus,
  SellerProfile,
  approveListing,
  getReviewQueue,
  getSellerProfile,
  rejectListing,
} from "@/lib/api";
import { useStore } from "@/lib/store";

const TABS: ListingStatus[] = ["pending", "approved", "rejected"];

export default function Admin() {
  const { session } = useStore();
  const [profile, setProfile] = useState<SellerProfile | null | undefined>(undefined);
  const [tab, setTab] = useState<ListingStatus>("pending");
  const [listings, setListings] = useState<Listing[] | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!session?.token) return setProfile(null);
    getSellerProfile().then(setProfile);
  }, [session?.token]);

  useEffect(() => {
    if (!profile?.is_admin) return;
    setListings(null);
    getReviewQueue(tab).then(setListings);
  }, [profile?.is_admin, tab]);

  async function approve(id: string) {
    setBusy(true);
    await approveListing(id);
    setListings((l) => (l ?? []).filter((x) => x.id !== id));
    setBusy(false);
  }

  async function reject(id: string) {
    setBusy(true);
    await rejectListing(id, note.trim());
    setListings((l) => (l ?? []).filter((x) => x.id !== id));
    setRejecting(null);
    setNote("");
    setBusy(false);
  }

  if (profile === undefined) {
    return (
      <>
        <TopBar />
        <main className="flex-1 px-6"><div className="mt-10 h-32 animate-pulse bg-mist" /></main>
        <BottomNav />
      </>
    );
  }

  if (!profile?.is_admin) {
    return (
      <>
        <TopBar />
        <main className="flex-1 px-6 pb-6">
          <h1 className="text-center text-[17px] font-bold lowercase">review queue</h1>
          <p className="mt-14 text-center text-[14px] text-faint">
            {profile ? "This account isn't a moderator." : (
              <><Link href="/login" className="text-ink underline">Log in</Link> to continue.</>
            )}
          </p>
        </main>
        <BottomNav />
      </>
    );
  }

  return (
    <>
      <TopBar />
      <main className="flex-1 px-6 pb-6">
        <h1 className="text-center text-[17px] font-bold lowercase">review queue</h1>

        <div className="mt-4 flex justify-center gap-2 text-[12px]">
          {TABS.map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              aria-pressed={tab === t}
              className={`border px-3 py-1 ${
                tab === t ? "border-ink bg-ink text-paper" : "border-ink/50 hover:bg-mist"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {listings === null ? (
          <div className="mt-6 space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-24 animate-pulse bg-mist" />
            ))}
          </div>
        ) : listings.length === 0 ? (
          <p className="mt-12 text-center text-[14px] text-faint">
            {tab === "pending" ? "Queue is clear." : `No ${tab} listings.`}
          </p>
        ) : (
          <ul className="mt-5 divide-y divide-line">
            {listings.map((l) => (
              <li key={l.id} className="py-4">
                <div className="flex items-start gap-4">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={l.image_url} alt="" className="h-24 w-20 bg-mist object-cover" />
                  <div className="min-w-0 flex-1 text-[13px]">
                    <div className="flex items-center gap-2">
                      <p className="truncate font-medium">{l.name}</p>
                      <StatusBadge status={l.status} />
                    </div>
                    <p className="text-[11px] uppercase tracking-micro text-faint">
                      {l.category} · {l.brand_name}
                    </p>
                    {l.caption && <p className="mt-1 text-[12px] italic text-ink/75">{l.caption}</p>}
                    {l.review_note && (
                      <p className="mt-1 text-[12px] italic text-signal">Note: {l.review_note}</p>
                    )}
                  </div>
                  <span className="text-[14px]">${l.price.toFixed(2)}</span>
                </div>

                {tab === "pending" && (
                  rejecting === l.id ? (
                    <div className="mt-3 flex gap-2">
                      <input
                        autoFocus
                        value={note}
                        onChange={(e) => setNote(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && reject(l.id)}
                        placeholder="Why? (shown to the seller)"
                        className="min-w-0 flex-1 border border-ink/50 px-2 py-1 text-[12px] focus:border-ink focus:outline-none"
                      />
                      <button
                        onClick={() => reject(l.id)}
                        disabled={busy}
                        className="shrink-0 border border-signal px-3 py-1 text-[12px] text-signal disabled:opacity-50"
                      >
                        Send
                      </button>
                      <button
                        onClick={() => { setRejecting(null); setNote(""); }}
                        className="shrink-0 text-[12px] text-faint underline"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="mt-3 flex gap-2">
                      <button
                        onClick={() => approve(l.id)}
                        disabled={busy}
                        className="bg-ink px-4 py-1.5 text-[12px] uppercase tracking-micro text-paper hover:bg-ink/85 disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => setRejecting(l.id)}
                        className="border border-ink/50 px-4 py-1.5 text-[12px] uppercase tracking-micro hover:bg-mist"
                      >
                        Request changes
                      </button>
                    </div>
                  )
                )}
              </li>
            ))}
          </ul>
        )}
      </main>
      <BottomNav />
    </>
  );
}
