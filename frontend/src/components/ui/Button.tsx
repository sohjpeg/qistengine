import { cva, type VariantProps } from "class-variance-authority";
import { forwardRef } from "react";
import { cn } from "@/lib/utils";

const button = cva(
  "inline-flex items-center justify-center gap-2 rounded-sm font-medium transition-tokens disabled:opacity-50 disabled:pointer-events-none whitespace-nowrap",
  {
    variants: {
      variant: {
        primary: "bg-brand text-white hover:bg-brand-hover",
        secondary: "bg-surface text-ink border border-rule-strong hover:bg-surface-sunk",
        ghost: "bg-transparent text-ink-muted hover:bg-surface-sunk hover:text-ink",
        danger: "bg-band-very-high text-white hover:opacity-90",
        quiet: "bg-surface-sunk text-ink hover:bg-brand-tint",
      },
      size: {
        sm: "h-[34px] px-3 text-body",
        md: "h-[38px] px-4 text-body",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof button> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button ref={ref} className={cn(button({ variant, size }), className)} {...props} />
  ),
);
Button.displayName = "Button";
