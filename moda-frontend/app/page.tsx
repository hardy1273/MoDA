import Link from "next/link";
import { Logo } from "@/components/Logo";

export default function Splash() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 px-8 text-center">
      <Logo size={120} />
      <p className="text-[15px] text-ink/80">Discover fashion tailored to your style.</p>
      <Link
        href="/signup"
        className="rounded-full bg-ink px-7 py-2.5 text-[14px] text-paper hover:bg-ink/85"
      >
        Get started
      </Link>
    </main>
  );
}
