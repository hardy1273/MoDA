"use client";

import Link from "next/link";
import { BottomNav } from "@/components/BottomNav";
import { TopBar } from "@/components/TopBar";
import { useStore } from "@/lib/store";

export default function Profile() {
  const { session, setSession, liked, saved } = useStore();

  return (
    <>
      <TopBar />
      <main className="flex-1 px-7 pb-6">
        <h1 className="text-center text-[17px] font-bold lowercase">profile</h1>

        <div className="mt-8 text-center">
          <p className="text-[16px] font-semibold">{session?.username ?? "Guest"}</p>
          {session?.profileText && (
            <p className="mx-auto mt-3 max-w-[300px] font-display text-[16px] italic leading-relaxed text-ink/80">
              “{session.profileText}”
            </p>
          )}
        </div>

        <dl className="mx-auto mt-8 flex max-w-[260px] justify-between text-center text-[13px]">
          <div><dt className="font-semibold">{Object.keys(liked).length}</dt><dd className="text-faint">liked</dd></div>
          <div><dt className="font-semibold">{Object.keys(saved).length}</dt><dd className="text-faint">saved</dd></div>
        </dl>

        <div className="mt-10 flex flex-col items-center gap-3 text-[13px]">
          <Link href="/orders" className="underline">Order history</Link>
          <Link href="/quiz" className="underline">Retake style quiz</Link>
          <button
            onClick={() => setSession(null)}
            className="text-faint underline"
          >
            Sign out
          </button>
        </div>
      </main>
      <BottomNav />
    </>
  );
}
