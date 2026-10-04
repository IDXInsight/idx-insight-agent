"use client";

import * as React from "react";
import Link from "next/link";
import { motion, useReducedMotion, type HTMLMotionProps, type Variants } from "motion/react";
import { cn } from "@/lib/utils";

type FlipDirection = "top" | "bottom" | "left" | "right";

type FlipContent = {
  label: string;
  icon?: React.ReactNode;
  iconPosition?: "start" | "end";
};

interface FlipButtonProps extends Omit<HTMLMotionProps<"button">, "children">, FlipContent {
  from?: FlipDirection;
}

type FlipLinkProps = Omit<React.ComponentProps<typeof Link>, "children"> & FlipContent;

const FlipButton = React.forwardRef<HTMLButtonElement, FlipButtonProps>(function FlipButton(
  { label, icon, iconPosition = "end", from = "top", className, disabled, ...props }, ref,
) {
  const reducedMotion = useReducedMotion();
  const vertical = from === "top" || from === "bottom";
  const turn = from === "top" || from === "left" ? -78 : 78;
  const labelVariants: Variants = {
    initial: { rotateX: 0, rotateY: 0, y: 0 },
    hover: {
      rotateX: vertical ? [0, turn, 0] : 0,
      rotateY: vertical ? 0 : [0, turn, 0],
      y: [0, -2, 0],
      transition: { duration: .46, ease: "easeInOut" },
    },
  };

  return <motion.button
    ref={ref}
    type="button"
    initial="initial"
    whileHover={!disabled && !reducedMotion ? "hover" : undefined}
    whileFocus={!disabled && !reducedMotion ? "hover" : undefined}
    whileTap={!disabled && !reducedMotion ? { scale: .97 } : undefined}
    disabled={disabled}
    className={cn("flip-action", className)}
    {...props}
  >
    <motion.span className="flip-label" variants={labelVariants}>{iconPosition === "start" && icon}{label}{iconPosition === "end" && icon}</motion.span>
  </motion.button>;
});
FlipButton.displayName = "FlipButton";

function FlipLink({ label, icon, iconPosition = "end", className, ...props }: FlipLinkProps) {
  return <Link className={cn("flip-action flip-link", className)} {...props}>
    <span className="flip-label">{iconPosition === "start" && icon}{label}{iconPosition === "end" && icon}</span>
  </Link>;
}

export { FlipButton, FlipLink, type FlipButtonProps, type FlipLinkProps, type FlipDirection };
