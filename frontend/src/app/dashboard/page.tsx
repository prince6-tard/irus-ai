"use client";

import { useEffect, useState } from "react";
import LogStream from "@/components/LogStream";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const POLL_INTERVAL = 3000;

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

interface Draft {
  timestamp: string;
  email: string;
  name: string;
  organization: string;
  subject: string;
  body: string;
  status: string;
  lead_json?: string;
}

interface CampaignResult {
  status?: string;
  message?: string;
  leads_found?: number;
  leads_enriched?: number;
  leads_processed?: number;
  drafted?: number;
  sent?: number;
  skipped?: number;
  errors?: number;
  dry_run?: boolean;
  review_before_send?: boolean;
}

export default function Dashboard() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [status, setStatus] = useState<{ running: boolean; last_result: CampaignResult | null }>({
    running: false,
    last_result: null,
  });
  const [error, setError] = useState("");
  const [sendingAll, setSendingAll] = useState(false);
  const [sendingOne, setSendingOne] = useState<string | null>(null);
  const [editingDraft, setEditingDraft] = useState<Draft | null>(null);
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [activeTab, setActiveTab] = useState<"logs" | "drafts">("drafts");

  // Polling
  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const [logsRes, statusRes, draftsRes] = await Promise.all([
          fetch(`${API_BASE}/logs`),
          fetch(`${API_BASE}/status`),
          fetch(`${API_BASE}/drafts/pending`),
        ]);

        if (!cancelled) {
          const logsData = await logsRes.json();
          const statusData = await statusRes.json();
          const draftsData = await draftsRes.json();

          if (logsData.status === "success") setLogs(logsData.logs || []);
          if (statusData.status === "success") {
            setStatus({ running: statusData.running, last_result: statusData.last_result });
          }
          if (draftsData.status === "success") setDrafts(draftsData.drafts || []);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(err.message || "Failed to fetch data");
        }
      }
    };

    fetchData();
    const interval = setInterval(fetchData, POLL_INTERVAL);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  const handleSendOne = async (email: string) => {
    setSendingOne(email);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/drafts/${encodeURIComponent(email)}/send`, { method: "POST" });
      const data = await res.json();
      if (data.status !== "success") {
        setError(data.message || "Failed to send");
      }
    } catch (err: any) {
      setError(err.message || "Send error");
    }
    setSendingOne(null);
  };

  const handleSendAll = async () => {
    setSendingAll(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/drafts/send-all`, { method: "POST" });
      const data = await res.json();
      if (data.status === "started") {
        alert("Sending all emails in the background...");
      } else {
        setError(data.message || "Failed to send all");
      }
    } catch (err: any) {
      setError(err.message || "Send all error");
    }
    setSendingAll(false);
  };

  const openEditModal = (draft: Draft) => {
    setEditingDraft(draft);
    setEditSubject(draft.subject || "");
    setEditBody(draft.body || "");
  };

  const closeEditModal = () => {
    setEditingDraft(null);
    setEditSubject("");
    setEditBody("");
  };

  const saveEdit = async () => {
    if (!editingDraft) return;
    try {
      const res = await fetch(`${API_BASE}/drafts/${encodeURIComponent(editingDraft.email)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ subject: editSubject, body: editBody }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setDrafts((prev) =>
          prev.map((d) =>
            d.email === editingDraft.email
              ? { ...d, subject: editSubject, body: editBody, status: "edited" }
              : d
          )
        );
        closeEditModal();
      } else {
        setError(data.message || "Update failed");
      }
    } catch (err: any) {
      setError(err.message || "Update error");
    }
  };

  const result = status.last_result;
  const pendingCount = drafts.filter((d) => ["drafted", "edited"].includes(d.status)).length;
  const sentCount = drafts.filter((d) => d.status === "sent").length;
  const failedCount = drafts.filter((d) => d.status === "failed").length;

  return (
    <main className="relative min-h-screen flex flex-col px-6 py-10">
      {/* Header */}
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Live Dashboard</h1>
          <p className="mt-1 text-sm text-white/50">Real-time pipeline progress and activity logs</p>
        </div>
        <div className="flex items-center gap-3">
          {status.running && (
            <span className="flex items-center gap-2 rounded-full bg-amber-400/10 border border-amber-400/20 px-3 py-1 text-xs font-medium text-amber-300">
              <span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75"></span><span className="relative inline-flex h-2 w-2 rounded-full bg-amber-400"></span></span>
              Running
            </span>
          )}
          {result && (
            <span className={`rounded-full px-3 py-1 text-xs font-medium border ${result.drafted && pendingCount > 0 ? 'bg-sky-400/10 text-sky-300 border-sky-400/20' : 'bg-emerald-400/10 text-emerald-300 border-emerald-400/20'}`}>
              {pendingCount > 0 ? `${pendingCount} Ready to Send` : sentCount > 0 ? 'Sent' : 'Completed'}
            </span>
          )}
          {!status.running && !result && (
            <span className="rounded-full bg-white/5 border border-white/10 px-3 py-1 text-xs font-medium text-white/40">Idle</span>
          )}
        </div>
      </header>

      {error && (
        <div className="mb-6 w-full rounded-lg border border-red-400/30 bg-red-400/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Campaign Metrics */}
      {result && (
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <MetricCard label="Leads Found" value={result.leads_found ?? 0} />
          <MetricCard label="Enriched" value={result.leads_enriched ?? 0} />
          <MetricCard label="Drafted" value={result.drafted ?? 0} />
          <MetricCard label="Ready to Send" value={pendingCount} />
          <MetricCard label="Sent" value={sentCount} />
          <MetricCard label="Failed" value={failedCount} />
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 mb-4 border-b border-white/10 pb-2">
        <button
          onClick={() => setActiveTab("drafts")}
          className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${activeTab === "drafts" ? "bg-sky-500/20 text-sky-300 border border-sky-400/20" : "text-white/60 hover:text-white hover:bg-white/5"}`}
        >
          Review & Send {pendingCount > 0 && <span className="ml-1 text-[10px] bg-sky-400/20 px-1.5 py-0.5 rounded-full">{pendingCount}</span>}
        </button>
        <button
          onClick={() => setActiveTab("logs")}
          className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${activeTab === "logs" ? "bg-white/10 text-white border border-white/20" : "text-white/60 hover:text-white hover:bg-white/5"}`}
        >
          Activity Log
        </button>
      </div>

      {/* Drafts Panel */}
      {activeTab === "drafts" && (
        <div className="flex-1 animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-sm font-semibold text-white/80 uppercase tracking-wider">AI Drafted Emails</h2>
              <p className="text-[11px] text-white/30">Review each email before sending. Click Edit to override the AI draft.</p>
            </div>
            {pendingCount > 0 && (
              <button
                onClick={handleSendAll}
                disabled={sendingAll}
                className={`glass-btn rounded-lg px-5 py-2 text-sm font-bold text-white ${sendingAll ? "opacity-60 cursor-wait" : ""}`}
              >
                {sendingAll ? "Sending..." : `Send All (${pendingCount})`}
              </button>
            )}
          </div>

          {drafts.length === 0 ? (
            <div className="glass-card rounded-xl p-10 text-center">
              <p className="text-white/40 text-sm">No drafted emails yet. Launch a campaign to see AI-drafted emails here.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {drafts.map((draft) => (
                <div key={draft.email} className="glass rounded-xl p-5">
                  <div className="flex flex-col sm:flex-row sm:items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-white">{draft.name || draft.email}</span>
                        <span className="text-[10px] text-white/30">|</span>
                        <span className="text-xs text-white/50">{draft.organization}</span>
                        <span className="text-[10px] text-white/30">|</span>
                        <span className={`inline-block rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider border ${
                          draft.status === 'drafted'
                            ? 'text-amber-400 bg-amber-400/10 border-amber-400/20'
                            : draft.status === 'edited'
                            ? 'text-sky-400 bg-sky-400/10 border-sky-400/20'
                            : draft.status === 'sent'
                            ? 'text-emerald-400 bg-emerald-400/10 border-emerald-400/20'
                            : 'text-red-400 bg-red-400/10 border-red-400/20'
                        }`}>
                          {draft.status}
                        </span>
                      </div>
                      <div className="mb-2">
                        <span className="text-[10px] text-white/30 uppercase tracking-widest">Subject</span>
                        <p className="text-sm text-white font-medium mt-0.5">
                          {draft.subject || "—"}
                        </p>
                      </div>
                      <div>
                        <span className="text-[10px] text-white/30 uppercase tracking-widest">Body</span>
                        <div className="mt-1 text-xs text-white/70 whitespace-pre-wrap max-h-32 overflow-y-auto scrollbar-thin glass-card p-3 rounded-lg">
                          {draft.body || "—"}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 shrink-0">
                      {["drafted", "edited"].includes(draft.status) && (
                        <>
                          <button
                            onClick={() => openEditModal(draft)}
                            className="rounded-lg bg-white/5 border border-white/10 px-4 py-2 text-xs font-medium text-white/80 hover:bg-white/10 transition-colors"
                          >
                            Edit
                          </button>
                          <button
                            onClick={() => handleSendOne(draft.email)}
                            disabled={sendingOne === draft.email}
                            className={`glass-btn rounded-lg px-4 py-2 text-xs font-bold text-white ${sendingOne === draft.email ? "opacity-60 cursor-wait" : ""}`}
                          >
                            {sendingOne === draft.email ? "Sending..." : "Send"}
                          </button>
                        </>
                      )}
                      {draft.status === "sent" && (
                        <span className="text-[10px] text-emerald-400 font-medium">✓ Sent</span>
                      )}
                      {draft.status === "failed" && (
                        <span className="text-[10px] text-red-400 font-medium">✗ Failed</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Logs Panel */}
      {activeTab === "logs" && (
        <div className="flex-1 animate-fade-in">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-white/80 uppercase tracking-wider">Activity Log</h2>
            <span className="text-[10px] text-white/30">Polling every {POLL_INTERVAL / 1000}s</span>
          </div>
          <LogStream logs={logs} />
        </div>
      )}

      {/* Edit Modal */}
      {editingDraft && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
          <div className="glass-strong w-full max-w-2xl max-h-[90vh] overflow-y-auto rounded-2xl p-6 space-y-4">
            <h3 className="text-lg font-bold text-white">Edit Email for {editingDraft.name || editingDraft.email}</h3>
            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-1">Subject</label>
              <input
                type="text"
                value={editSubject}
                onChange={(e) => setEditSubject(e.target.value)}
                className="glass-input w-full rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <div>
              <label className="block text-[10px] uppercase tracking-widest text-white/40 mb-1">Body</label>
              <textarea
                value={editBody}
                onChange={(e) => setEditBody(e.target.value)}
                rows={12}
                className="glass-input w-full rounded-lg px-3 py-2 text-sm text-white"
              />
            </div>
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={closeEditModal}
                className="rounded-lg bg-white/5 border border-white/10 px-5 py-2 text-sm font-medium text-white/60 hover:text-white hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={saveEdit}
                className="glass-btn rounded-lg px-5 py-2 text-sm font-bold text-white"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

function MetricCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="glass-card rounded-xl px-4 py-3 text-center">
      <div className="text-xl font-bold text-white">{value}</div>
      <div className="mt-0.5 text-[10px] uppercase tracking-wider text-white/40">{label}</div>
    </div>
  );
}
