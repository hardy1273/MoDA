"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/Logo";
import { login } from "@/lib/api";
import { useStore } from "@/lib/store";

const inputCls =
  "w-full rounded-lg border border-ink/70 px-4 py-3 text-[14px] placeholder:text-faint focus:border-ink";

export default function Login() {
  const router = useRouter();
  const { setSession } = useStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (!email.includes("@") || !password) {
      setError("Enter your email and password.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const { user, token } = await login(email.trim(), password);
      setSession({
        userId: user.id,
        username: user.username,
        profileText: user.profile_text,
        token,
      });
      // Users with a profile go straight to their feed; new-ish ones to the quiz
      router.push(user.profile_text ? "/feed" : "/quiz");
    } catch (e) {
      setError(
        e instanceof Error && e.message.startsWith("401")
          ? "Incorrect email or password."
          : "Login failed — is the backend running?",
      );
      setBusy(false);
    }
  }

  return (
    <main className="flex flex-1 flex-col px-7 pt-6">
      <Logo />
      <div className="flex flex-1 flex-col justify-center gap-4 pb-16">
        <h1 className="mb-2 text-center text-[20px] font-medium">Login</h1>
        <input className={inputCls} placeholder="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        <input
          className={inputCls}
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />

        {error && <p className="text-center text-[13px] text-signal">{error}</p>}

        <p className="text-center text-[13px]">
          New here? <Link href="/signup" className="underline">Sign up.</Link>
        </p>
        <button
          onClick={submit}
          disabled={busy}
          className="mx-auto mt-2 rounded-full bg-ink px-9 py-2.5 text-[14px] text-paper hover:bg-ink/85 disabled:opacity-50"
        >
          {busy ? "Logging in…" : "Continue"}
        </button>
      </div>
    </main>
  );
}
