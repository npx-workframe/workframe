import Image from "next/image";
import Link from "next/link";

const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? "https://app.[redacted]";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col bg-[#0A0A0F] text-white">
      <header className="safe-top flex items-center justify-between px-5 py-4">
        <div className="flex items-center gap-3">
          <Image src="/icon.svg" alt="" width={28} height={28} priority />
          <span className="text-sm font-semibold tracking-wide">Workframe</span>
        </div>
        <Link
          href={appUrl}
          className="rounded-full border border-white/15 px-4 py-2 text-sm font-medium text-white/90"
        >
          Open app
        </Link>
      </header>

      <main className="flex flex-1 flex-col justify-center gap-8 px-5 pb-10">
        <div className="space-y-4">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-violet-300/80">
            Agent cockpit for teams
          </p>
          <h1 className="max-w-xl text-4xl font-semibold leading-tight tracking-tight sm:text-5xl">
            Run agents together. Ship from files, not transcripts.
          </h1>
          <p className="max-w-lg text-base leading-7 text-white/65">
            Workframe is the multi-user Hermes cockpit — rooms, vault, delegation,
            and durable handoffs for technical teams.
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <Link
            href={appUrl}
            className="inline-flex h-12 items-center justify-center rounded-full bg-white px-6 text-sm font-semibold text-[#0A0A0F]"
          >
            Get started
          </Link>
          <Link
            href="https://github.com/npx-workframe/workframe"
            className="inline-flex h-12 items-center justify-center rounded-full border border-white/15 px-6 text-sm font-medium text-white/90"
          >
            View on GitHub
          </Link>
        </div>
      </main>

      <footer className="safe-bottom border-t border-white/10 px-5 py-4 text-xs text-white/45">
        Public marketing surface · product app lives at app.[redacted]
      </footer>
    </div>
  );
}
