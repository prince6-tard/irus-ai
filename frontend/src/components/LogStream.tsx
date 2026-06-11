"use client";

import { useEffect, useRef } from "react";

interface LogEntry {
  timestamp: string;
  email: string;
  name: string;
  organization: string;
  status: string;
  subject: string;
  note: string;
  apollo_id: string;
}

interface LogStreamProps {
  logs: LogEntry[];
}

const statusColors: Record<string, string> = {
  sent: "text-emerald-400 bg-emerald-400/10 border-emerald-400/20",
  dry_run: "text-amber-400 bg-amber-400/10 border-amber-400/20",
  skipped_no_email: "text-red-400 bg-red-400/10 border-red-400/20",
  skipped_already_sent: "text-orange-400 bg-orange-400/10 border-orange-400/20",
  error_draft: "text-rose-400 bg-rose-400/10 border-rose-400/20",
  error_send: "text-rose-400 bg-rose-400/10 border-rose-400/20",
};

export default function LogStream({ logs }: LogStreamProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  if (logs.length === 0) {
    return (
      <div className="glass-card rounded-xl p-8 text-center">
        <p className="text-white/40 text-sm">No pipeline logs yet. Launch a campaign to see live activity.</p>
      </div>
    );
  }

  return (
    <div className="glass rounded-xl overflow-hidden max-h-[70vh] flex flex-col">
      <div className="overflow-y-auto p-4 space-y-2 scrollbar-thin">
        {logs.map((log, idx) => {
          const badgeClass =
            statusColors[log.status] ||
            "text-white/60 bg-white/5 border-white/10";

          return (
            <div
              key={`${log.timestamp}-${idx}`}
              className="flex items-start gap-3 rounded-lg bg-white/[0.03] px-4 py-3 hover:bg-white/[0.05] transition-colors"
            >
              <div className="mt-0.5 shrink-0">
                <span
                  className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${badgeClass}`}
                >
                  {log.status.replace(/_/g, " ")}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs">
                  <span className="text-white font-medium truncate">
                    {log.name || "Unknown"}
                  </span>
                  <span className="text-white/30">|</span>
                  <span className="text-white/50 truncate">{log.email}</span>
                  <span className="text-white/30">|</span>
                  <span className="text-white/50 truncate">{log.organization}</span>
                </div>
                {log.subject && (
                  <p className="mt-1 text-[11px] text-white/40 truncate">
                    Subject: {log.subject}
                  </p>
                )}
                {log.note && (
                  <p className="mt-0.5 text-[11px] text-white/30 truncate">
                    {log.note}
                  </p>
                )}
              </div>
              <div className="shrink-0 text-[10px] text-white/20 tabular-nums">
                {new Date(log.timestamp).toLocaleTimeString()}
              </div>
            </div>
          );
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
