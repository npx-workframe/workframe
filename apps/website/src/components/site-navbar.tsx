import Image from "next/image";
import Link from "next/link";

function GithubIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 19 19" fill="currentColor" aria-hidden className={className}>
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M9.356 1.85C5.05 1.85 1.57 5.356 1.57 9.694a7.84 7.84 0 0 0 5.324 7.44c.387.079.528-.168.528-.376 0-.182-.013-.805-.013-1.454-2.165.467-2.616-.935-2.616-.935-.349-.91-.864-1.143-.864-1.143-.71-.48.051-.48.051-.48.787.051 1.2.805 1.2.805.695 1.194 1.817.857 2.268.649.064-.507.27-.857.49-1.052-1.728-.182-3.545-.857-3.545-3.87 0-.857.31-1.558.8-2.104-.078-.195-.349-1 .077-2.078 0 0 .657-.208 2.14.805a7.5 7.5 0 0 1 1.946-.26c.657 0 1.328.092 1.946.26 1.483-1.013 2.14-.805 2.14-.805.426 1.078.155 1.883.078 2.078.502.546.799 1.247.799 2.104 0 3.013-1.818 3.675-3.558 3.87.284.247.528.714.528 1.454 0 1.052-.012 1.896-.012 2.156 0 .208.142.455.528.377a7.84 7.84 0 0 0 5.324-7.441c.013-4.338-3.48-7.844-7.773-7.844"
      />
    </svg>
  );
}

export function SiteNavbar({
  wide = false,
  docsActive = false,
}: {
  wide?: boolean;
  docsActive?: boolean;
}) {
  return (
    <header className="wf-page-bg safe-top w-full">
      <nav
        className={`mx-auto flex w-full items-center justify-between px-6 py-5 sm:px-10 ${
          wide ? "max-w-6xl" : "max-w-3xl"
        }`}
      >
        <Link href="/" className="flex cursor-pointer items-center gap-2.5">
          <Image
            src="/workframe-color.svg"
            alt=""
            width={24}
            height={24}
            priority
            className="h-6 w-6 shrink-0"
          />
          <Image
            src="/wordmark.svg"
            alt="Workframe"
            width={132}
            height={18}
            priority
            className="h-[15px] w-auto opacity-50"
          />
        </Link>

        <div className="flex items-center gap-5">
          <Link
            href="https://github.com/npx-workframe/workframe"
            aria-label="GitHub"
            className="cursor-pointer text-[var(--wf-text)] opacity-50 transition-opacity hover:opacity-70"
          >
            <GithubIcon className="h-5 w-5" />
          </Link>
          <Link
            href="/docs"
            className={`cursor-pointer text-[13px] font-medium transition-opacity hover:opacity-80 ${
              docsActive
                ? "text-[var(--wf-text)] opacity-100"
                : "text-[var(--wf-text)] opacity-50"
            }`}
          >
            Docs
          </Link>
        </div>
      </nav>
    </header>
  );
}
