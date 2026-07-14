"use client";

// Style profile quiz.
// Steps follow the wireframe (aesthetic → fit → layering → color →
// occasions → brands → inspirations), then a "Your style profile" summary
// screen with edit affordances, then the feed. Brands and inspirations are
// optional free-text steps with suggestion chips.

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { Outfit, getSampleOutfits, submitQuiz } from "@/lib/api";
import { useStore } from "@/lib/store";

type StepKey =
  | "aesthetics"
  | "fits"
  | "layering"
  | "colors"
  | "occasions"
  | "brands"
  | "inspirations"
  | "calibration";

type StepDef = {
  key: StepKey;
  question: string;
  options: string[];
  multi: boolean;
  freeText?: boolean; // options become suggestions; user can also type their own
  images?: boolean; // options are outfit ids rendered as a photo grid
  hint?: string;
};

const STEPS: StepDef[] = [
  { key: "aesthetics", question: "what's your aesthetic?", options: ["modern", "vintage", "streetwear", "minimal", "old money", "techwear"], multi: true },
  { key: "fits", question: "how do you like the fit?", options: ["relaxed", "oversized", "slim", "tailored"], multi: true },
  { key: "layering", question: "do you layer?", options: ["yes", "no"], multi: false },
  { key: "colors", question: "your color profile?", options: ["monochrome", "neutrals", "earth tones", "pastels", "bold"], multi: true },
  { key: "occasions", question: "what are you dressing for?", options: ["everyday", "work", "formal", "nightlife", "casual", "travel"], multi: true },
  { key: "brands", question: "brands you love?", options: ["nike", "adidas", "uniqlo", "zara", "cos", "carhartt"], multi: true, freeText: true, hint: "optional — pick or type your own" },
  { key: "inspirations", question: "style inspirations?", options: ["90s hip hop", "parisian chic", "scandi minimalism", "y2k", "japanese streetwear"], multi: true, freeText: true, hint: "optional — an era, scene, or icon" },
  { key: "calibration", question: "pick the looks you love", options: [], multi: true, images: true, hint: "tap any that speak to you — this teaches MODA your eye" },
];

const EMPTY_PICKS: Record<StepKey, string[]> = {
  aesthetics: [],
  fits: [],
  layering: [],
  colors: [],
  occasions: [],
  brands: [],
  inspirations: [],
  calibration: [],
};

export default function Quiz() {
  const router = useRouter();
  const { session, setProfileText } = useStore();
  const [step, setStep] = useState(0);
  const [picks, setPicks] = useState<Record<StepKey, string[]>>(EMPTY_PICKS);
  const [phase, setPhase] = useState<"quiz" | "summary">("quiz");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState("");
  const [sample, setSample] = useState<Outfit[] | null>(null);

  const def = STEPS[step];

  // Fetch the calibration grid once, as soon as the quiz starts
  useEffect(() => {
    getSampleOutfits(12).then(setSample);
  }, []);

  function toggle(opt: string) {
    setPicks((p) => {
      const cur = p[def.key];
      if (!def.multi) return { ...p, [def.key]: [opt] };
      return { ...p, [def.key]: cur.includes(opt) ? cur.filter((x) => x !== opt) : [...cur, opt] };
    });
  }

  function addDraft() {
    const v = draft.trim().toLowerCase();
    if (!v) return;
    setPicks((p) =>
      p[def.key].includes(v) ? p : { ...p, [def.key]: [...p[def.key], v] },
    );
    setDraft("");
  }

  function next() {
    setDraft("");
    if (step < STEPS.length - 1) setStep(step + 1);
    else setPhase("summary");
  }

  async function finish() {
    setBusy(true);
    const profile = await submitQuiz({
      aesthetics: picks.aesthetics,
      fits: picks.fits,
      colors: picks.colors,
      occasions: picks.occasions.length ? picks.occasions : ["everyday"],
      brands: picks.brands,
      inspirations: picks.inspirations,
      likedOutfitIds: picks.calibration,
      layering: picks.layering[0] === "yes",
    });
    setProfileText(profile);
    router.push("/feed");
  }

  const summaryRows: { label: string; value: string; jump: number }[] = [
    { label: "style", value: picks.aesthetics.join(", ") || "—", jump: 0 },
    { label: "fit", value: picks.fits.join(", ") || "—", jump: 1 },
    { label: "layering", value: picks.layering[0] ?? "—", jump: 2 },
    { label: "color profile", value: picks.colors.join(", ") || "—", jump: 3 },
    { label: "occasions", value: picks.occasions.join(", ") || "—", jump: 4 },
    { label: "brands", value: picks.brands.join(", ") || "—", jump: 5 },
    { label: "inspirations", value: picks.inspirations.join(", ") || "—", jump: 6 },
    { label: "looks you loved", value: picks.calibration.length ? `${picks.calibration.length} picked` : "—", jump: 7 },
  ];

  // Free-text picks that aren't in the suggestion list still need a chip
  const visibleOptions = def.freeText
    ? [...def.options, ...picks[def.key].filter((v) => !def.options.includes(v))]
    : def.options;

  return (
    <main className="flex flex-1 flex-col px-7 pt-6">
      <Logo />
      <h1 className="mt-10 text-center font-display text-[34px] font-semibold italic">Style profile</h1>
      <p className="mt-1 text-center text-[11px] italic text-faint">
        Complete this survey for recommendations tailored to your taste!
      </p>

      {phase === "quiz" ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-8 pb-20">
          <div className="text-center">
            <h2 className="font-display text-[22px] italic">{def.question}</h2>
            {def.hint && <p className="mt-1 text-[11px] italic text-faint">{def.hint}</p>}
          </div>
          {def.images ? (
            sample === null ? (
              <div className="grid w-full max-w-md grid-cols-3 gap-2">
                {Array.from({ length: 12 }).map((_, i) => (
                  <div key={i} className="aspect-[3/4] animate-pulse bg-mist" />
                ))}
              </div>
            ) : (
              <div className="grid w-full max-w-md grid-cols-3 gap-2">
                {sample.map((o) => {
                  const active = picks.calibration.includes(o.id);
                  return (
                    <button
                      key={o.id}
                      onClick={() => toggle(o.id)}
                      aria-pressed={active}
                      className={`relative overflow-hidden border-2 transition-colors ${
                        active ? "border-ink" : "border-transparent"
                      }`}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={o.image_url}
                        alt={o.caption ?? "Outfit"}
                        className="aspect-[3/4] w-full object-cover"
                      />
                      {active && (
                        <span className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full bg-ink text-[11px] text-paper">
                          ✓
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            )
          ) : (
            <div className="flex max-w-md flex-wrap justify-center gap-3">
              {visibleOptions.map((opt) => {
                const active = picks[def.key].includes(opt);
                return (
                  <button
                    key={opt}
                    onClick={() => toggle(opt)}
                    aria-pressed={active}
                    className={`rounded-lg border px-5 py-2 text-[15px] font-semibold transition-colors ${
                      active ? "border-ink bg-mist" : "border-ink/60 bg-paper hover:bg-mist/60"
                    }`}
                  >
                    {opt}
                  </button>
                );
              })}
            </div>
          )}
          {def.freeText && (
            <div className="flex items-center gap-2">
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addDraft();
                  }
                }}
                placeholder="type your own…"
                aria-label={`Add your own ${def.key.slice(0, -1)}`}
                className="rounded-lg border border-ink/60 bg-paper px-4 py-2 text-[14px] outline-none placeholder:italic placeholder:text-faint focus:border-ink"
              />
              <button
                onClick={addDraft}
                className="rounded-lg border border-ink/60 px-3 py-2 text-[14px] font-semibold hover:bg-mist"
              >
                add
              </button>
            </div>
          )}
          <button onClick={next} className="text-[12px] italic text-faint underline-offset-2 hover:underline">
            skip
          </button>
          <button
            onClick={next}
            className="rounded-full bg-ink px-7 py-2.5 text-[14px] text-paper hover:bg-ink/85"
          >
            next →
          </button>
          <p className="text-[12px] italic text-faint">step {step + 1}/{STEPS.length}</p>
        </div>
      ) : (
        <div className="flex flex-1 flex-col items-center justify-center gap-7 pb-20">
          <h2 className="text-[17px] font-semibold">Your style profile</h2>
          <dl className="flex flex-col items-center gap-4">
            {summaryRows.map((row) => (
              <div key={row.label} className="text-center">
                <dt className="text-[15px] font-semibold">{row.label}</dt>
                <dd className="mt-0.5 flex items-center justify-center gap-2 text-[14px] text-ink/80">
                  {row.value}
                  <button
                    aria-label={`Edit ${row.label}`}
                    onClick={() => {
                      setStep(row.jump);
                      setPhase("quiz");
                    }}
                    className="text-ink/50 hover:text-ink"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                      <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
                    </svg>
                  </button>
                </dd>
              </div>
            ))}
          </dl>
          <button
            onClick={finish}
            disabled={busy}
            className="mt-2 rounded-full bg-ink px-6 py-2.5 text-[13px] font-semibold text-paper hover:bg-ink/85 disabled:opacity-50"
          >
            {busy ? "building your feed…" : "go to personalized feed"}
          </button>
        </div>
      )}
    </main>
  );
}
