import { ButtonHTMLAttributes } from "react";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "accept";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  fullWidth?: boolean;
}

const variantStyles: Record<ButtonVariant, string> = {
  primary: "bg-[#2563EB] text-white hover:bg-[#1D4ED8] border border-transparent",
  secondary: "bg-white text-[#0F172A] border border-[#CBD5E1] hover:bg-[#F8FAFC]",
  ghost: "bg-transparent text-[#475569] border border-[#E2E8F0] hover:bg-[#F1F5F9]",
  danger: "bg-white text-[#EF4444] border border-transparent hover:bg-[#FEE2E2]",
  accept: "bg-[#16A3A1] text-white hover:bg-[#0F8E8C] border border-transparent",
};

export function Button({
  variant = "primary",
  fullWidth = false,
  className = "",
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={[
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5",
        "text-sm font-medium transition-colors duration-150",
        "focus:outline-none focus:ring-2 focus:ring-[#2563EB] focus:ring-offset-1",
        "disabled:opacity-50 disabled:cursor-not-allowed",
        variantStyles[variant],
        fullWidth ? "w-full" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      disabled={disabled}
      {...props}
    >
      {children}
    </button>
  );
}
