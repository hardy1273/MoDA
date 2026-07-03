"use client";

// Style profile quiz.
// Steps follow the wireframe (aesthetic → fit → layering → color), then a
// "Your style profile" summary screen with edit affordances, then the feed.

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/Logo";
import { submitQuiz } from "@/lib/api";
import { useStore } from "@/lib/store";

type StepDef = {
  key: "aesthetics" | "fits" | "layering" | "colors";
  question: string;
  options: string[];
  multi: boolean;
};

const STEPS: StepDef[] = [
  { key: "aesthetics", question: "what's your aesthetic?", options: ["modern", "vintage", "streetwear", "minimal", "old money", "techwear"], multi: true },
  { key: "fits", question: "how do you like the fit?", options: ["relaxed", "oversized", "slim", "tailored"], multi: true },
  { key: "layering", question: "do you layer?", options: ["yes", "no"], multi: false },
  { key: "colors", question: "your color profile?", options: ["monochrome", "neutrals", "earth tones", "pastels", "bold"], multi: true },
];

export default function Quiz() {
  const router = useRouter();
  const { session, setProfileText } = useStore();
  const [step, setStep] = useState(0);
  const [picks, setPicks] = useState<Record<string, string[]>>({
    aesthetics: [],
    fits: [],
    layering: [],
    colors: [],
  });
  const [phase, setPhase] = useState<"quiz" | "summary">("quiz");
  const [busy, setBusy] = useState(false);

  const def = STEPS[step];

  function toggle(opt: string) {
    setPicks((p) => {
      const cur = p[def.key];
      if (!def.multi) return { ...p, [def.key]: [opt] };
      return { ...p, [def.key]: cur.includes(opt) ? cur.filter((x) => x !== opt) : [...cur, opt] };
    });
  }

  function next() {
    if (step < STEPS.length - 1) setStep(step + 1);
    else setPhase("summary");
  }

  async function finish() {
    setBusy(true);
    const userId = session?.userId ?? "demo-user";
    const profile = await submitQuiz(userId, {
      aesthetics: picks.aesthetics,
      fits: picks.fits,
      colors: picks.colors,
      occasions: ["everyday"],
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
  ];

  return (
    <main className="flex flex-1 flex-col px-7 pt-6">
      <Logo />
      <h1 className="mt-10 text-center font-display text-[34px] font-semibold italic">Style profile</h1>
      <p className="mt-1 text-center text-[11px] italic text-faint">
        Complete this survey for recommendations tailored to your taste!
      </p>

      {phase === "quiz" ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-8 pb-20">
          <h2 className="font-display text-[22px] italic">{def.question}</h2>
          <div className="flex flex-wrap justify-center gap-3">
            {def.options.map((opt) => {
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
          <dl className="flex flex-col items-center gap-5">
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
