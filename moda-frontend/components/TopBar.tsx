"use client";

import Link from "next/link";
import { Logo } from "./Logo";
import { useStore } from "@/lib/store";

export function TopBar() {
  const { cartCount } = useStore();
  return (
    <header className="flex items-center justify-between px-5 pt-5 pb-3">
      <Link href="/feed" aria-label="MODA home" className="text-ink">
        <Logo />
      </Link>
      <nav className="flex items-center gap-4">
        <Link href="/quiz" aria-label="Retake style quiz" className="p-1">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
          </svg>
        </Link>
        <Link href="/profile" aria-label="Profile" className="p-1">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 5-5.5 8-5.5s6.5 1.5 8 5.5" />
          </svg>
        </Link>
        <Link href="/cart" aria-label={`Cart, ${cartCount} items`} className="relative p-1">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M6 7h12l-1.3 12.1a1.5 1.5 0 0 1-1.5 1.4H8.8a1.5 1.5 0 0 1-1.5-1.4L6 7Z" />
            <path d="M9 7a3 3 0 0 1 6 0" />
          </svg>
          {cartCount > 0 && (
            <span className="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-ink text-[10px] leading-none text-paper">
              {cartCount}
            </span>
          )}
        </Link>
      </nav>
    </header>
  );
}
