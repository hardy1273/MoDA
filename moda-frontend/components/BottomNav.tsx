"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/feed", label: "Home" },
  { href: "/explore", label: "Explore" },
  { href: "/closet", label: "Closet" },
  { href: "/profile", label: "Profile" },
];

export function BottomNav() {
  const path = usePathname();
  return (
    <nav className="sticky bottom-0 z-10 border-t border-line bg-paper">
      <div className="flex items-center justify-around py-3 text-[13px]">
        {items.map((it) => {
          const active = path?.startsWith(it.href);
          return (
            <Link
              key={it.href}
              href={it.href}
              className={active ? "font-semibold underline underline-offset-4" : "text-faint hover:text-ink"}
            >
              {it.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
