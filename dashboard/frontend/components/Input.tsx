"use client";

import * as React from "react";
import { cn } from "@/lib/utils";

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, label, id, ...props }, ref) => {
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
        <input
          id={inputId}
          type={type}
          className={cn(
            "w-full bg-white text-[15px] text-[#0a0a0a] px-3 py-2.5 rounded-lg",
            "border border-[#e3e8ee]",
            "outline-none focus:border-[#8b8b8b] transition-colors",
            "placeholder:text-[#9b9b9b]",
            "disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-[#f6f8fa]",
            error && "border-[#ef4444] focus:border-[#ef4444]",
            className
          )}
          ref={ref}
          {...props}
        />
        {error && (
          <p className="mt-2 text-[11px] text-[#ef4444] tracking-[0.03em] font-light">{error}</p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };

