import * as React from "react";
import { cn } from "@/lib/utils/cn";

type BadgeVariant = "default" | "secondary" | "success" | "warning" | "destructive";

const variantClasses: Record<BadgeVariant, string> = {
  default: "bg-primary/10 text-primary border-primary/30",
  secondary: "bg-muted text-muted-foreground border-border",
  success: "bg-emerald-500/10 text-emerald-600 border-emerald-500/30",
  warning: "bg-amber-500/10 text-amber-600 border-amber-500/30",
  destructive: "bg-destructive/10 text-destructive border-destructive/30",
};

export function Badge({
  className,
  variant = "default",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2 py-0.5 text-sm font-medium",
        variantClasses[variant],
        className
      )}
      {...props}
    />
  );
}
