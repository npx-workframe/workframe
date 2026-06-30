type ShellFooterProps = {
  status?: string
}

/** Status chrome — badges and live state land here in a later slice. */
export function ShellFooter({ status }: ShellFooterProps) {
  return (
    <footer className="wf-shell__footer" aria-label="Status">
      <output className="wf-shell-footer__status" aria-live="polite">
        {status ?? ''}
      </output>
    </footer>
  )
}
