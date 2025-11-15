"use client";

import { ButtonHTMLAttributes, ReactNode } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "neutral";
  size?: "sm" | "md" | "lg";
  icon?: ReactNode;
  children: ReactNode;
}

export default function Button({
  variant = "primary",
  size = "md",
  icon,
  children,
  className = "",
  disabled,
  ...props
}: ButtonProps) {
  const baseStyles =
    "inline-flex items-center justify-center gap-1.5 rounded-[10px] transition-colors tracking-[0.03em] font-light disabled:opacity-50 disabled:cursor-not-allowed";

  const variantStyles = {
    primary: "bg-[#0a0a0a] text-white hover:bg-[#2a2a2a]",
    secondary:
      "bg-white text-[#0a0a0a] border border-[#e3e8ee] hover:border-[#8b8b8b]",
    ghost: "bg-transparent text-[#8b8b8b] hover:text-[#0a0a0a]",
    neutral: "bg-[#f7f7f7] text-[#0a0a0a] hover:bg-[#e3e8ee]",
  };

  const sizeStyles = {
    sm: "text-[11px] px-3 py-1.5",
    md: "text-[13px] px-4 py-2",
    lg: "text-[15px] px-5 py-2.5",
  };

  return (
    <button
      disabled={disabled}
      className={`${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`}
      {...props}
    >
      {icon && <span className="flex-shrink-0">{icon}</span>}
      {children}
    </button>
  );
}
