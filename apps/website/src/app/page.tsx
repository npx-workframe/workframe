import { CopyCommand } from "@/components/copy-command";
import { DemoVideo } from "@/components/demo-video";
import { SiteNavbar } from "@/components/site-navbar";

export default function Home() {
  return (
    <div className="flex min-h-dvh flex-col">
      <SiteNavbar />

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

      <footer className="safe-bottom mb-2.5 px-6 pb-12 pt-8 text-center font-[family-name:var(--wf-font-mono)] text-[11px] uppercase tracking-[0.12em] text-[var(--wf-muted)] sm:px-10 sm:pb-14">
        © 2026 Workfra.me
      </footer>
    </div>
  );
}
