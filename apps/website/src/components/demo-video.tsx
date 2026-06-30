"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const videoSrc =
  process.env.NEXT_PUBLIC_DEMO_VIDEO_URL ?? "/Workframe_DemoVideos.mp4";

type WebkitVideo = HTMLVideoElement & {
  webkitEnterFullscreen?: () => void;
  webkitExitFullscreen?: () => void;
  webkitDisplayingFullscreen?: boolean;
};

function isIosNativeFullscreen(video: HTMLVideoElement | null) {
  return !!(video as WebkitVideo | null)?.webkitDisplayingFullscreen;
}

function isFullscreen(video: HTMLVideoElement | null) {
  return !!document.fullscreenElement || isIosNativeFullscreen(video);
}

function formatTime(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function PlayIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden className={className}>
      <path d="M8 5.14v13.72c0 .79.87 1.27 1.54.84l11.14-6.86c.65-.4.65-1.28 0-1.68L9.54 4.3C8.87 3.87 8 4.35 8 5.14z" />
    </svg>
  );
}

function PauseIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden className={className}>
      <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
    </svg>
  );
}

function VolumeIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden className={className}>
      <path d="M11 5 6 9H2v6h4l5 4V5z" strokeLinejoin="round" />
      <path d="M15.54 8.46a5 5 0 0 1 0 7.07M17.07 6.93a8 8 0 0 1 0 11.32" strokeLinecap="round" />
    </svg>
  );
}

function VolumeMuteIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden className={className}>
      <path d="M11 5 6 9H2v6h4l5 4V5z" strokeLinejoin="round" />
      <path d="m22 9-6 6M16 9l6 6" strokeLinecap="round" />
    </svg>
  );
}

function ExpandIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden className={className}>
      <path d="M8 3H5a2 2 0 0 0-2 2v3M21 8V5a2 2 0 0 0-2-2h-3M3 16v3a2 2 0 0 0 2 2h3M16 21h3a2 2 0 0 0 2-2v-3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ShrinkIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden className={className}>
      <path d="M4 14h3v3M20 10h-3V7M10 20v-3H7M14 4v3h3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function ControlButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className="neo-raised flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-full border-0 text-[var(--wf-text)] transition-transform active:scale-95"
    >
      {children}
    </button>
  );
}

export function DemoVideo() {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [playing, setPlaying] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [showControls, setShowControls] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);

  const syncTimeline = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    setCurrentTime(video.currentTime);

    const seekableEnd =
      video.seekable.length > 0
        ? video.seekable.end(video.seekable.length - 1)
        : 0;
    const nextDuration =
      Number.isFinite(video.duration) && video.duration > 0
        ? video.duration
        : seekableEnd;

    if (Number.isFinite(nextDuration) && nextDuration > 0) {
      setDuration(nextDuration);
    }
  }, []);

  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  const bumpControls = useCallback(() => {
    setShowControls(true);
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    if (isFullscreen(videoRef.current)) return;
    hideTimerRef.current = setTimeout(() => setShowControls(false), 2800);
  }, []);

  const play = () => {
    void videoRef.current?.play();
  };

  const pause = () => {
    videoRef.current?.pause();
  };

  const toggle = () => {
    if (playing) pause();
    else play();
  };

  const seek = (clientX: number) => {
    const track = progressRef.current;
    const video = videoRef.current;
    if (!track || !video || !duration) return;
    const rect = track.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    video.currentTime = ratio * duration;
    setCurrentTime(video.currentTime);
  };

  const onProgressPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.stopPropagation();
    seek(e.clientX);
    const onMove = (ev: PointerEvent) => seek(ev.clientX);
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  };

  const toggleMute = () => {
    const video = videoRef.current;
    if (!video) return;
    video.muted = !video.muted;
    setMuted(video.muted);
  };

  const onVolumeChange = (value: number) => {
    const video = videoRef.current;
    if (!video) return;
    video.volume = value;
    video.muted = value === 0;
    setVolume(value);
    setMuted(value === 0);
  };

  const toggleFullscreen = async () => {
    const container = containerRef.current;
    const video = videoRef.current;
    if (!container || !video) return;

    const webkitVideo = video as WebkitVideo;

    try {
      if (isFullscreen(video)) {
        if (webkitVideo.webkitDisplayingFullscreen && webkitVideo.webkitExitFullscreen) {
          webkitVideo.webkitExitFullscreen();
        } else if (document.fullscreenElement) {
          await document.exitFullscreen();
        }
        return;
      }

      // iOS Safari — only the video element can enter native fullscreen
      if (webkitVideo.webkitEnterFullscreen) {
        webkitVideo.webkitEnterFullscreen();
        return;
      }

      if (container.requestFullscreen) {
        await container.requestFullscreen();
        return;
      }

      await video.requestFullscreen?.();
    } catch {
      /* denied or unsupported */
    }
  };

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const syncFullscreen = () => {
      const isFs = isFullscreen(video);
      setFullscreen(isFs);
      if (isFs) {
        setShowControls(true);
        if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
      }
    };

    document.addEventListener("fullscreenchange", syncFullscreen);
    video.addEventListener("webkitbeginfullscreen", syncFullscreen);
    video.addEventListener("webkitendfullscreen", syncFullscreen);
    return () => {
      document.removeEventListener("fullscreenchange", syncFullscreen);
      video.removeEventListener("webkitbeginfullscreen", syncFullscreen);
      video.removeEventListener("webkitendfullscreen", syncFullscreen);
    };
  }, []);

  useEffect(() => {
    if (playing) bumpControls();
    else setShowControls(false);
    return () => {
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, [playing, bumpControls]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = () => {
      syncTimeline();
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing, syncTimeline]);

  return (
    <div className="wf-video-shell w-full p-4">
      <div className="neo-elevated w-full overflow-hidden p-1.5">
        <div
          ref={containerRef}
          className="wf-video-stage group relative overflow-hidden rounded-[10px]"
          onMouseMove={() => playing && bumpControls()}
          onTouchStart={() => playing && bumpControls()}
        >
        <video
          ref={videoRef}
          className="wf-video-el block aspect-video w-full cursor-pointer bg-[var(--wf-surface)] object-cover"
          src={videoSrc}
          playsInline
          preload="metadata"
          onClick={toggle}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
          onLoadedMetadata={syncTimeline}
          onLoadedData={syncTimeline}
          onDurationChange={syncTimeline}
          onTimeUpdate={syncTimeline}
          onProgress={syncTimeline}
        >
          <track kind="captions" />
        </video>

        {!playing && (
          <>
            <div
              className="absolute inset-0 z-[1] bg-[var(--wf-surface)]"
              aria-hidden
            />
            <button
              type="button"
              aria-label="Play video"
              className="absolute inset-0 z-[2] flex cursor-pointer items-center justify-center border-0 bg-transparent p-0"
              onClick={play}
            >
              <span className="neo-raised flex h-16 w-16 items-center justify-center rounded-full text-[var(--wf-text)]">
                <PlayIcon className="h-7 w-7 -translate-x-1" />
              </span>
            </button>
          </>
        )}

        {playing && (
          <div
            className={`wf-video-controls pointer-events-none absolute inset-x-0 bottom-0 z-10 transition-opacity duration-300 ${
              showControls || fullscreen ? "opacity-100" : "opacity-0"
            }`}
          >
            <div className="pointer-events-auto px-3 pb-3">
              <div
                className="wf-video-controls-bar neo-raised flex cursor-pointer items-center gap-2 rounded-full bg-[var(--wf-surface)] px-3 py-2"
                onClick={(e) => e.stopPropagation()}
              >
                <ControlButton label={playing ? "Pause" : "Play"} onClick={toggle}>
                  {playing ? <PauseIcon /> : <PlayIcon />}
                </ControlButton>

                <span className="shrink-0 font-mono text-[11px] tabular-nums text-[var(--wf-muted)]">
                  {formatTime(currentTime)}
                  <span className="text-[var(--wf-muted)]/50"> / </span>
                  {formatTime(duration)}
                </span>

                <div
                  ref={progressRef}
                  role="slider"
                  aria-label="Seek"
                  aria-valuemin={0}
                  aria-valuemax={duration}
                  aria-valuenow={currentTime}
                  className="neo-inset relative h-2 min-w-0 flex-1 cursor-pointer rounded-full"
                  onPointerDown={onProgressPointerDown}
                >
                  <div
                    className="absolute inset-y-0 left-0 rounded-full bg-[var(--wf-text)]/30"
                    style={{ width: `${progress}%` }}
                  />
                  <div
                    className="neo-raised absolute top-1/2 h-3 w-3 -translate-y-1/2 rounded-full"
                    style={{ left: `calc(${progress}% - 6px)` }}
                  />
                </div>

                <ControlButton label={muted ? "Unmute" : "Mute"} onClick={toggleMute}>
                  {muted || volume === 0 ? <VolumeMuteIcon /> : <VolumeIcon />}
                </ControlButton>

                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={muted ? 0 : volume}
                  aria-label="Volume"
                  onChange={(e) => onVolumeChange(Number(e.target.value))}
                  onClick={(e) => e.stopPropagation()}
                  className="wf-video-range hidden w-16 shrink-0 sm:block"
                />

                <ControlButton
                  label={fullscreen ? "Exit fullscreen" : "Fullscreen"}
                  onClick={() => void toggleFullscreen()}
                >
                  {fullscreen ? <ShrinkIcon /> : <ExpandIcon />}
                </ControlButton>
              </div>
            </div>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}
