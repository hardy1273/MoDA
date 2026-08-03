"use client";

// Payouts section of the seller dashboard: set-up prompt when the seller
// can't be paid yet, earnings summary and history once they can.

import { useCallback, useEffect, useState } from "react";
import {
  Earnings,
  PayoutStatus,
  getEarnings,
  getPayoutStatus,
  retryPayouts,
  startPayoutOnboarding,
} from "@/lib/api";

const money = (n: number) => `$${n.toFixed(2)}`;

export function PayoutsPanel() {
  const [status, setStatus] = useState<PayoutStatus | null>(null);
  const [earnings, setEarnings] = useState<Earnings | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [s, e] = await Promise.all([getPayoutStatus(), getEarnings()]);
    setStatus(s);
    setEarnings(e);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function setUpPayouts() {
    setBusy(true);
    setError(null);
    try {
      const r = await startPayoutOnboarding();
      if (r.url) {
        // Stripe-hosted onboarding; they come back to /sell?payouts=done
        window.location.href = r.url;
        return;
      }
      // Simulated provider — nothing to visit, settle anything owed
      await retryPayouts();
      await load();
    } catch {
      setError("Couldn't start payout setup. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  }

  async function settleNow() {
    setBusy(true);
    setError(null);
    try {
      await retryPayouts();
      await load();
    } catch {
      setError("Couldn't release payouts. Try again in a moment.");
    } finally {
      setBusy(false);
    }
  }

  if (!status) return null;

  const pending = status.pending_cents / 100;
  const paid = status.paid_cents / 100;

  return (
    <section className="mt-7 border border-line p-4">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="font-display text-[18px] font-semibold italic">Payouts</h2>
        {status.simulated && (
          <span className="shrink-0 border border-ink/40 px-1.5 py-0.5 text-[10px] uppercase tracking-micro text-faint">
            test mode
          </span>
        )}
      </div>

      {!status.payouts_enabled ? (
        <>
          <p className="mt-2 text-[13px] text-faint">
            Set up payouts to get paid for your sales. You keep{" "}
            <strong className="text-ink">90%</strong> of every sale; MODA takes 10%.
          </p>
          {pending > 0 && (
            <p className="mt-2 text-[13px]">
              <strong>{money(pending)}</strong> is waiting for you — it&apos;ll be released
              once setup is done.
            </p>
          )}
          {error && <p className="mt-2 text-[13px] text-signal">{error}</p>}
          <button
            onClick={setUpPayouts}
            disabled={busy}
            className="mt-3 w-full bg-ink py-3 text-[13px] uppercase tracking-micro text-paper hover:bg-ink/85 disabled:opacity-50"
          >
            {busy ? "Opening…" : status.onboarding_started ? "Finish payout setup" : "Set up payouts"}
          </button>
          {status.simulated && (
            <p className="mt-2 text-[11px] italic text-faint">
              No Stripe key configured, so setup completes instantly and no real money moves.
            </p>
          )}
        </>
      ) : (
        <>
          <dl className="mt-3 flex gap-6 text-[13px]">
            <div>
              <dt className="text-faint">Paid out</dt>
              <dd className="text-[16px] tabular-nums">{money(paid)}</dd>
            </div>
            <div>
              <dt className="text-faint">Pending</dt>
              <dd className="text-[16px] tabular-nums">{money(pending)}</dd>
            </div>
            {earnings && (
              <div>
                <dt className="text-faint">Fees paid</dt>
                <dd className="text-[16px] tabular-nums">{money(earnings.lifetime_fees)}</dd>
              </div>
            )}
          </dl>

          {error && <p className="mt-2 text-[13px] text-signal">{error}</p>}
          {pending > 0 && (
            <button
              onClick={settleNow}
              disabled={busy}
              className="mt-3 border border-ink px-4 py-1.5 text-[12px] uppercase tracking-micro hover:bg-ink hover:text-paper disabled:opacity-50"
            >
              {busy ? "Releasing…" : "Release pending"}
            </button>
          )}

          {earnings && earnings.payouts.length > 0 && (
            <ul className="mt-4 divide-y divide-line border-t border-line">
              {earnings.payouts.slice(0, 8).map((p) => (
                <li key={p.id} className="flex items-baseline justify-between gap-3 py-2 text-[13px]">
                  <span className="text-faint tabular-nums">
                    {new Date(p.created_at).toLocaleDateString(undefined, {
                      month: "short",
                      day: "numeric",
                    })}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-faint">
                    {money(p.gross)} − {money(p.fee)} fee
                  </span>
                  <span className="tabular-nums">{money(p.net)}</span>
                  <span
                    className={`shrink-0 text-[10px] uppercase tracking-micro ${
                      p.status === "paid" ? "text-faint" : "text-signal"
                    }`}
                  >
                    {p.status}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
