"use client";

interface ProductTileProps {
  name: string;
  description: string;
  selected: boolean;
  onToggle: () => void;
}

export default function ProductTile({
  name,
  description,
  selected,
  onToggle,
}: ProductTileProps) {
  const shortDesc =
    description.length > 140
      ? description.substring(0, 140).trim() + "..."
      : description;

  return (
    <button
      onClick={onToggle}
      className={`glass-card rounded-xl p-5 text-left w-full transition-all duration-300 ${
        selected ? "selected" : ""
      }`}
    >
      <div className="flex items-start gap-4">
        <div
          className={`mt-1 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-colors ${
            selected
              ? "border-sky-400 bg-sky-400/20"
              : "border-white/20 bg-white/5"
          }`}
        >
          {selected && (
            <svg
              className="h-3.5 w-3.5 text-sky-300"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={3}
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M5 13l4 4L19 7"
              />
            </svg>
          )}
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-white tracking-wide">
            {name}
          </h3>
          <p className="mt-1.5 text-xs leading-relaxed text-white/60">
            {shortDesc}
          </p>
        </div>
      </div>
    </button>
  );
}
