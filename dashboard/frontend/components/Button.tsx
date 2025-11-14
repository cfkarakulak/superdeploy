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
    "inline-flex items-center justify-center",
    "focus-visible:outline-none focus-visible:ring-0",
    "disabled:opacity-50 disabled:pointer-events-none disabled:cursor-not-allowed",
    "-webkit-tap-highlight-color-transparent",
    "relative",
    "overflow-hidden",
    "border-0",
    "cursor-pointer",
    "select-none"
  );

  const sizeClasses = {
    sm: "h-[56px] px-[20px] py-[12px] text-[15px] font-semibold",
    md: "h-[56px] px-[20px] py-[12px] text-[15px] font-semibold",
    lg: "h-[56px] px-[20px] py-[12px] text-[15px] font-semibold",
  };

  const radiusClasses = {
    sm: "rounded-[20px]",
    md: "rounded-[20px]",
    lg: "rounded-[20px]",
  };

  const variants = {
    default: cn(
      "bg-[#292933] text-[#fff]",
      "hover:bg-[#222]",
      "transition-all duration-150 ease-in-out"
    ),
    secondary: cn(
      "bg-[#f7f7f7] text-[#15291f]",
      "hover:bg-[#ebebeb]",
      "border border-[#e3e8ee]",
      "transition-all duration-150 ease-in-out"
    ),
    outline: cn(
      "border border-[#00d66f] text-[#00d66f] bg-transparent",
      "hover:bg-[#00d66f] hover:text-[#15291f]",
      "transition-all duration-150 ease-in-out"
    ),
    ghost: cn(
      "text-[#525252] bg-transparent",
      "hover:bg-[#f7f7f7]",
      "transition-all duration-150 ease-in-out"
    ),
    destructive: cn(
      "bg-[#df1b41] text-white",
      "hover:bg-[#c41635]",
      "transition-all duration-150 ease-in-out"
    ),
    success: cn(
      "bg-[#00d66f] text-[#15291f]",
      "hover:bg-[#00c263]",
      "transition-all duration-150 ease-in-out"
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
