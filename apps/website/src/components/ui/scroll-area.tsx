import { forwardRef, type ComponentPropsWithoutRef } from "react";

import { cn } from "@/lib/utils";

import "@/styles/scroll-area.css";

export const scrollAreaClass = "wf-scroll";

type ScrollAreaAxis = "vertical" | "horizontal" | "both";

type ScrollAreaProps = ComponentPropsWithoutRef<"div"> & {
  axis?: ScrollAreaAxis;
};

const axisClass: Record<ScrollAreaAxis, string> = {
  vertical: "wf-scroll--vertical",
  horizontal: "wf-scroll--horizontal",
  both: "wf-scroll--both",
};

export const ScrollArea = forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ axis = "both", className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        scrollAreaClass,
        axisClass[axis],
        axis !== "horizontal" && "wf-scroll-host",
        className,
      )}
      {...props}
    />
  ),
);
ScrollArea.displayName = "ScrollArea";
