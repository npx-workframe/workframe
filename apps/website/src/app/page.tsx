import Image from "next/image";
import Link from "next/link";

import { CopyCommand } from "@/components/copy-command";
import { DemoVideo } from "@/components/demo-video";

export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="safe-top flex items-center justify-between px-6 py-5 sm:px-10">
        <Image
          src="/wordmark.svg"
          alt="Workframe"
          width={132}
          height={18}
          priority
          className="h-[18px] w-auto"
        />
        <Link
          href="https://github.com/npx-workframe/workframe"
          className="text-[13px] font-medium text-[var(--wf-muted)] transition-colors hover:text-[var(--wf-text)]"
        >
          GitHub
        </Link>
      </header>

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col items-center gap-14 px-6 pb-16 pt-10 sm:gap-16 sm:px-10 sm:pt-14">
        <section className="flex w-full flex-col items-center gap-5 text-center">
          <h1 className="max-w-xl text-[2rem] font-semibold leading-[1.12] tracking-[-0.03em] text-[var(--wf-text)] sm:text-[2.75rem]">
            The Social OS for Autonomous Businesses
          </h1>
          <p className="max-w-md text-[17px] leading-7 text-[var(--wf-muted)] sm:text-[18px]">
            A private workspace where humans and agents collaborate through chat,
            boards, and files.
          </p>
        </section>

        <CopyCommand />

        <section className="w-full">
          <DemoVideo />
        </section>
      </main>

      <footer className="safe-bottom px-6 py-6 text-center text-[12px] text-[var(--wf-muted)] sm:px-10">
        Developed by Softsupply
      </footer>
    </div>
  );
}
