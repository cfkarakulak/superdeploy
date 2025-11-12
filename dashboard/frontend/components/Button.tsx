"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "secondary" | "outline" | "ghost" | "destructive" | "success";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

function Button({
  variant = "default",
  size = "md",
  loading = false,
  className,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const baseClasses = cn(
    "inline-flex items-center justify-center font-medium",
    "transition-all duration-200 ease-in-out",
    "focus-visible:outline-none",
    "disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed",
    "active:scale-[0.97]",
    "-webkit-tap-highlight-color-transparent",
    "hover:-translate-y-[1px]",
    "active:translate-y-0"
  );

  const sizeClasses = {
    sm: "h-9 px-4 text-sm",
    md: "h-11 px-6 text-base",
    lg: "h-12 px-8 text-base",
  };

  const radiusClasses = {
    sm: "rounded",
    md: "rounded-md",
    lg: "rounded-lg",
  };

  const variants = {
    default: cn(
      "bg-primary text-primary-foreground",
      "hover:bg-[#006635]",
      "shadow-[0_0_0_1px_rgba(0,0,0,.03),0_1px_0_rgba(0,0,0,.05)]",
      "hover:shadow-[0_0_0_1px_rgba(0,0,0,.03),0_2px_4px_rgba(0,0,0,.08)]",
      "focus-visible:shadow-[0_0_0_3px_rgba(0,133,69,0.1)]"
    ),
    secondary: cn(
      "bg-secondary text-secondary-foreground",
      "hover:bg-[#e6e6e6]",
      "border border-border",
      "shadow-[0_0_0_1px_rgba(0,0,0,.08)]",
      "hover:shadow-[0_0_0_1px_rgba(0,0,0,.08),0_2px_4px_rgba(0,0,0,.08)]",
      "focus-visible:shadow-[0_0_0_3px_rgba(0,0,0,0.05)]"
    ),
    outline: cn(
      "border border-primary text-primary bg-transparent",
      "hover:bg-primary hover:text-primary-foreground",
      "shadow-[0_0_0_1px_rgba(0,0,0,.08)]",
      "focus-visible:shadow-[0_0_0_3px_rgba(0,133,69,0.1)]"
    ),
    ghost: cn(
      "text-foreground bg-transparent",
      "hover:bg-muted",
      "focus-visible:shadow-[0_0_0_3px_rgba(0,0,0,0.05)]"
    ),
    destructive: cn(
      "bg-destructive text-destructive-foreground",
      "hover:bg-[#c41635]",
      "shadow-[0_0_0_1px_rgba(0,0,0,.03),0_1px_0_rgba(0,0,0,.05)]",
      "hover:shadow-[0_0_0_1px_rgba(0,0,0,.03),0_2px_4px_rgba(0,0,0,.08)]",
      "focus-visible:shadow-[0_0_0_3px_rgba(223,27,65,0.15)]"
    ),
    success: cn(
      "bg-success text-success-foreground",
      "hover:bg-[#006635]",
      "shadow-[0_0_0_1px_rgba(0,0,0,.03),0_1px_0_rgba(0,0,0,.05)]",
      "hover:shadow-[0_0_0_1px_rgba(0,0,0,.03),0_2px_4px_rgba(0,0,0,.08)]",
      "focus-visible:shadow-[0_0_0_3px_rgba(0,133,69,0.1)]"
    ),
  };

  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={cn(
        baseClasses,
        sizeClasses[size],
        radiusClasses[size],
        variants[variant],
        className
      )}
      {...props}
    >
      {loading ? (
        <>
          <svg
            className="animate-spin -ml-1 mr-2 h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          Loading...
        </>
      ) : (
        children
      )}
    </button>
  );
}

export { Button };
