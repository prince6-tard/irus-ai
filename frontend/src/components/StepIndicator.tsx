"use client";

interface StepIndicatorProps {
  steps: string[];
  currentStep: number;
}

export default function StepIndicator({ steps, currentStep }: StepIndicatorProps) {
  return (
    <nav className="w-full max-w-2xl mx-auto mb-10">
      <ol className="flex items-center justify-between">
        {steps.map((label, idx) => {
          const stepNum = idx + 1;
          const isActive = stepNum === currentStep;
          const isCompleted = stepNum < currentStep;

          return (
            <li key={label} className="flex flex-1 items-center">
              <div className="flex flex-col items-center gap-2 w-full">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-bold transition-all duration-300 ${
                    isCompleted
                      ? "bg-sky-500/20 text-sky-300 border border-sky-400/40"
                      : isActive
                      ? "bg-white/10 text-white border border-white/30 shadow-[0_0_12px_rgba(14,165,233,0.25)]"
                      : "bg-white/5 text-white/40 border border-white/10"
                  }`}
                >
                  {isCompleted ? (
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2.5}
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M5 13l4 4L19 7"
                      />
                    </svg>
                  ) : (
                    stepNum
                  )}
                </div>
                <span
                  className={`text-[10px] uppercase tracking-widest font-medium transition-colors ${
                    isActive ? "text-white/80" : "text-white/30"
                  }`}
                >
                  {label}
                </span>
              </div>
              {idx < steps.length - 1 && (
                <div className="mx-2 h-px flex-1 bg-white/10 min-w-[2rem]" />
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
