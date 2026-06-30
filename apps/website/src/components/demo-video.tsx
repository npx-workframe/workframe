const videoSrc =
  process.env.NEXT_PUBLIC_DEMO_VIDEO_URL ?? "/demo.mp4";

export function DemoVideo() {
  return (
    <div className="neo-elevated w-full overflow-hidden p-1.5">
      <div className="neo-inset overflow-hidden rounded-[10px]">
        <video
          className="block aspect-video w-full bg-[var(--wf-surface)] object-cover"
          src={videoSrc}
          poster="/demo-poster.png"
          controls
          playsInline
          preload="metadata"
        >
          <track kind="captions" />
        </video>
      </div>
    </div>
  );
}
