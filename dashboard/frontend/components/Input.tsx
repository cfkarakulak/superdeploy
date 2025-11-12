"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, label, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm font-medium mb-2 text-foreground">
            {label}
          </label>
        )}
        <input
          type={type}
          className={cn(
            "flex h-11 w-full bg-white px-4 py-3 text-base text-foreground",
            "border border-input rounded-md",
            "shadow-[0_0_0_1px_rgba(0,0,0,.08)]",
            "transition-all duration-200 ease-out",
            "file:border-0 file:bg-transparent file:text-sm file:font-medium",
            "placeholder:text-muted-foreground",
            "focus-visible:outline-none focus-visible:border-primary",
            "focus-visible:shadow-[0_0_0_3px_rgba(0,133,69,0.1)]",
            "focus-visible:-translate-y-[1px]",
            "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-muted",
            error && "border-destructive focus-visible:border-destructive focus-visible:shadow-[0_0_0_3px_rgba(223,27,65,0.15)]",
            className
          )}
          ref={ref}
          {...props}
        />
        {error && (
          <p className="mt-2 text-sm text-destructive font-medium">{error}</p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };

