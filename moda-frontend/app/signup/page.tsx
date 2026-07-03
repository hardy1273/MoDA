"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/Logo";
import { createUser } from "@/lib/api";
import { useStore } from "@/lib/store";

const inputCls =
  "w-full rounded-lg border border-ink/70 px-4 py-3 text-[14px] placeholder:text-faint focus:border-ink";

export default function SignUp() {
  const router = useRouter();
  const { setSession } = useStore();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!name.trim() || !email.includes("@")) {
      setError("Enter a name and a valid email to continue.");
      return;
    }
    if (password.length > 0 && password !== confirm) {
      setError("Passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    const user = await createUser(name.trim().toLowerCase().replace(/\s+/g, "_"), email.trim());
    setSession({ userId: user.id, username: name.trim(), profileText: null });
    router.push("/quiz");
  }

  return (
    <main className="flex flex-1 flex-col px-7 pt-6">
      <Logo />
      <div className="flex flex-1 flex-col justify-center gap-4 pb-16">
        <h1 className="mb-2 text-center text-[20px] font-medium">Sign up</h1>
        <input className={inputCls} placeholder="Name" value={name} onChange={(e) => setName(e.target.value)} />
        <input className={inputCls} placeholder="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className={inputCls} placeholder="Password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
        <input className={inputCls} placeholder="Confirm password" type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />

        {error && <p className="text-center text-[13px] text-signal">{error}</p>}

        <p className="text-center text-[13px]">
          Already have an account? <span className="underline">Login.</span>
        </p>
        <button
          onClick={submit}
          disabled={busy}
          className="mx-auto mt-2 rounded-full bg-ink px-9 py-2.5 text-[14px] text-paper hover:bg-ink/85 disabled:opacity-50"
        >
          {busy ? "Creating…" : "Continue"}
        </button>
      </div>
    </main>
  );
}
