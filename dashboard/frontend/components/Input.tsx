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
        <div
          className={cn(
            "bg-[#f7f7f7] rounded-[12px] px-3 py-2.5 transition-all duration-200 cursor-text",
            "focus-within:bg-white",
            "focus-within:outline focus-within:outline-2 focus-within:outline-[#00d66f]",
            error && "focus-within:outline-[#ef4444]"
          )}
          onClick={() => {
            const input = document.getElementById(inputId);
            input?.focus();
          }}
        >
          {label && (
            <label 
              htmlFor={inputId}
              className="block text-[13px] text-[#6b6b6b] mb-1 cursor-text"
            >
              {label}
            </label>
          )}
          <input
            id={inputId}
            type={type}
            className={cn(
              "w-full bg-transparent text-[15px] text-[#0a0a0a]",
              "border-none outline-none p-0 m-0",
              "placeholder:text-[#9b9b9b]",
              "disabled:cursor-not-allowed disabled:opacity-50",
              className
            )}
            ref={ref}
            {...props}
          />
        </div>
        {error && (
          <p className="mt-2 text-sm text-[#ef4444]">{error}</p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

export { Input };

