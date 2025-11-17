"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string | React.ReactNode;
  hint?: string;
  rightIcon?: React.ReactNode;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, label, hint, rightIcon, id, ...props }, ref) => {
    const inputId = id || React.useId();
    
    return (
      <div className="w-full">
        {label && (
          <label 
            htmlFor={inputId}
            className="block text-[11px] text-[#111] tracking-[0.03em] font-light mb-2"
          >
            {label}
          </label>
        )}
        <div className="relative">
          <input
            id={inputId}
            type={type}
            className={cn(
              "w-full bg-white text-[14px] text-[#0a0a0a] px-3 py-2 rounded-lg shadow-[inset_0_0_0_1px_rgba(10,10,46,0.14)] transition-colors focus:shadow-[0_0_0_2px_#93a2ae]",
              " border-none",
              "outline-none focus:border-[#8b8b8b] transition-colors",
              "placeholder:text-[#9b9b9b]",
              "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-[#f6f8fa]",
              "font-mono",
              error && "border-[#ef4444] focus:border-[#ef4444]",
              rightIcon && "pr-10",
              className
            )}
            ref={ref}
            {...props}
          />
          {rightIcon && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              {rightIcon}
            </div>
          )}
        </div>
        {hint && !error && (
          <p className="mt-1.5 text-[11px] text-[#8b8b8b] tracking-[0.03em] font-light">{hint}</p>
        )}
        {error && (
          <p className="mt-2 text-[11px] text-[#ef4444] tracking-[0.03em] font-light">{error}</p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };

