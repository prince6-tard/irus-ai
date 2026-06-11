import { ReactNode } from "react";

interface GlassCardProps {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
  selected?: boolean;
  strong?: boolean;
}

export default function GlassCard({
  children,
  className = "",
  onClick,
  selected = false,
  strong = false,
}: GlassCardProps) {
  const base = strong ? "glass-strong" : "glass-card";
  const selectClass = selected ? "selected" : "";
  const cursor = onClick ? "cursor-pointer" : "";

  return (
    <div
      onClick={onClick}
      className={`${base} ${selectClass} ${cursor} rounded-2xl p-6 ${className}`}
    >
      {children}
    </div>
  );
}
