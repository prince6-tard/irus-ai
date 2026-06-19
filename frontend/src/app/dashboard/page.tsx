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

interface Lead {
  id: number;
  name: string;
  email: string;
  email_source: string;
  phone: string;
  has_phone: boolean;
  organization: string;
  organization_domain: string;
  role: string;
  category: string;
  linkedin_url: string;
  city: string;
  country: string;
  apollo_id: string;
  notes: string;
  source: string;
  created_at: string;
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

interface SendResult {
  sent: number;
  failed: number;
  skipped: number;
}

export default function Dashboard() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [leadCategory, setLeadCategory] = useState<string>("");
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
  const [activeTab, setActiveTab] = useState<"logs" | "drafts" | "infos" | "upload">("drafts");
  const [selectedLeadIds, setSelectedLeadIds] = useState<number[]>([]);
  const [infosProducts, setInfosProducts] = useState<string[]>([]);
  const [infosSending, setInfosSending] = useState(false);
  const [sendResult, setSendResult] = useState<SendResult | null>(null);
  const [products, setProducts] = useState<string[]>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{ inserted: number; skipped: number; leads: Lead[] } | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Polling
  useEffect(() => {
    let cancelled = false;

    const fetchData = async () => {
      try {
        const catQuery = leadCategory ? `?category=${encodeURIComponent(leadCategory)}` : "";
        const [logsRes, statusRes, draftsRes, leadsRes, productsRes] = await Promise.all([
          fetch(`${API_BASE}/logs`),
          fetch(`${API_BASE}/status`),
          fetch(`${API_BASE}/drafts`),
          fetch(`${API_BASE}/leads${catQuery}`),
          fetch(`${API_BASE}/products`),
        ]);

        if (!cancelled) {
          const logsData = await logsRes.json();
          const statusData = await statusRes.json();
          const draftsData = await draftsRes.json();
          const leadsData = await leadsRes.json();

          if (logsData.status === "success") setLogs(logsData.logs || []);
          if (statusData.status === "success") {
            setStatus({ running: statusData.running, last_result: statusData.last_result });
          }
          if (draftsData.status === "success") setDrafts(draftsData.drafts || []);
          if (leadsData.status === "success") setLeads(leadsData.leads || []);
          if (productsRes.ok) {
            const productsData = await productsRes.json();
            let productList: string[] = [];
            if (Array.isArray(productsData)) {
              productList = productsData.map((p: any) => (typeof p === "string" ? p : p.product_name || p.name || String(p)));
            } else if (productsData.products && Array.isArray(productsData.products)) {
              productList = productsData.products.map((p: any) => (typeof p === "string" ? p : p.product_name || p.name || String(p)));
            }
            setProducts(productList);
          }
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
  }, [leadCategory]);

  const handleSendOne = async (email: string) => {
    setSendingOne(email);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/drafts/${encodeURIComponent(email)}/send`, { method: "POST" });
      const data = await res.json();
      if (data.status !== "success") {
        setError(data.message || "Failed to send");
      } else {
        setSuccessMsg(data.message || `Sent to ${email}`);
        setTimeout(() => setSuccessMsg(null), 3000);
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

  const handleSendSelected = async () => {
    if (selectedLeadIds.length === 0 || infosProducts.length === 0) return;
    setInfosSending(true);
    setError("");
    setSendResult(null);
    try {
      const res = await fetch(`${API_BASE}/leads/send-selected`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lead_ids: selectedLeadIds, selected_products: infosProducts, dry_run: false }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setSendResult({ sent: data.sent ?? 0, failed: data.failed ?? 0, skipped: data.skipped ?? 0 });
        setSelectedLeadIds([]);
      } else {
        setError(data.message || "Failed to send selected leads");
      }
    } catch (err: any) {
      setError(err.message || "Send selected error");
    }
    setInfosSending(false);
  };

  const handleSendAllLeads = async () => {
    if (leads.length === 0 || infosProducts.length === 0) return;
    const allIds = leads.map((l) => l.id);
    setSelectedLeadIds(allIds);
    setInfosSending(true);
    setError("");
    setSendResult(null);
    try {
      const res = await fetch(`${API_BASE}/leads/send-selected`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lead_ids: allIds, selected_products: infosProducts, dry_run: false }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setSendResult({ sent: data.sent ?? 0, failed: data.failed ?? 0, skipped: data.skipped ?? 0 });
        setSelectedLeadIds([]);
      } else {
        setError(data.message || "Failed to send all leads");
      }
    } catch (err: any) {
      setError(err.message || "Send all error");
    }
    setInfosSending(false);
  };

  const handleUpload = async () => {
    if (!uploadFile) return;
    setUploading(true);
    setError("");
    setUploadResult(null);
    try {
      const formData = new FormData();
      formData.append("file", uploadFile);
      const res = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.status === "success") {
        setUploadResult({
          inserted: data.inserted ?? 0,
          skipped: data.skipped ?? 0,
          leads: data.leads || [],
        });
      } else {
        setError(data.message || "Upload failed");
      }
    } catch (err: any) {
      setError(err.message || "Upload error");
    }
    setUploading(false);
  };

  const toggleLeadSelection = (leadId: number) => {
    setSelectedLeadIds((prev) =>
      prev.includes(leadId) ? prev.filter((id) => id !== leadId) : [...prev, leadId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedLeadIds.length === leads.length) {
      setSelectedLeadIds([]);
    } else {
      setSelectedLeadIds(leads.map((l) => l.id));
    }
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

      {successMsg && (
        <div className="mb-6 w-full rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-300">
          {successMsg}
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
          onClick={() => setActiveTab("infos")}
          className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${activeTab === "infos" ? "bg-emerald-500/20 text-emerald-300 border border-emerald-400/20" : "text-white/60 hover:text-white hover:bg-white/5"}`}
        >
          Infos {leads.length > 0 && <span className="ml-1 text-[10px] bg-emerald-400/20 px-1.5 py-0.5 rounded-full">{leads.length}</span>}
        </button>
        <button
          onClick={() => setActiveTab("logs")}
          className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${activeTab === "logs" ? "bg-white/10 text-white border border-white/20" : "text-white/60 hover:text-white hover:bg-white/5"}`}
        >
          Activity Log
        </button>
        <button
          onClick={() => setActiveTab("upload")}
          className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${activeTab === "upload" ? "bg-amber-500/20 text-amber-300 border border-amber-400/20" : "text-white/60 hover:text-white hover:bg-white/5"}`}
        >
          Upload
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

      {/* Infos Panel */}
      {activeTab === "infos" && (
        <div className="flex-1 animate-fade-in">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between mb-4 gap-3">
            <div>
              <h2 className="text-sm font-semibold text-white/80 uppercase tracking-wider">Lead Directory</h2>
              <p className="text-[11px] text-white/30">All scraped leads across campaigns</p>
            </div>
            <div className="flex items-center gap-2">
              {["", "Defence", "Medical"].map((cat) => (
                <button
                  key={cat || "all"}
                  onClick={() => setLeadCategory(cat)}
                  className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                    leadCategory === cat
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-400/20"
                      : "text-white/60 hover:text-white hover:bg-white/5 border border-transparent"
                  }`}
                >
                  {cat || "All"}
                </button>
              ))}
            </div>
          </div>

          {/* Product selector and Send button */}
          {leads.length > 0 && (
            <div className="mb-4 flex flex-col sm:flex-row items-start sm:items-center gap-3">
              <div className="flex items-center gap-2">
                <label className="text-xs text-white/50 uppercase tracking-wider">Products:</label>
                <select
                  multiple
                  value={infosProducts}
                  onChange={(e) => setInfosProducts(Array.from(e.target.selectedOptions, (o) => o.value))}
                  className="glass-input rounded-lg px-2 py-1.5 text-xs text-white max-h-24 overflow-y-auto"
                >
                  {products.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={handleSendSelected}
                disabled={selectedLeadIds.length === 0 || infosProducts.length === 0 || infosSending}
                className={`rounded-lg px-4 py-2 text-xs font-bold text-white transition-colors ${
                  selectedLeadIds.length === 0 || infosProducts.length === 0 || infosSending
                    ? "bg-white/5 border border-white/10 text-white/30 cursor-not-allowed"
                    : "bg-emerald-500/20 border border-emerald-400/30 text-emerald-300 hover:bg-emerald-500/30"
                }`}
              >
                {infosSending ? "Sending..." : `Send Selected (${selectedLeadIds.length})`}
              </button>
              <button
                onClick={handleSendAllLeads}
                disabled={leads.length === 0 || infosProducts.length === 0 || infosSending}
                className={`rounded-lg px-4 py-2 text-xs font-bold text-white transition-colors ${
                  leads.length === 0 || infosProducts.length === 0 || infosSending
                    ? "bg-white/5 border border-white/10 text-white/30 cursor-not-allowed"
                    : "bg-blue-500/20 border border-blue-400/30 text-blue-300 hover:bg-blue-500/30"
                }`}
              >
                {infosSending ? "Sending..." : `Send All (${leads.length})`}
              </button>
            </div>
          )}

          {/* Send result alert */}
          {sendResult && (
            <div className="mb-4 rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-300">
              Sent {sendResult.sent}, Failed {sendResult.failed}, Skipped {sendResult.skipped}
            </div>
          )}

          {leads.length === 0 ? (
            <div className="glass-card rounded-xl p-10 text-center">
              <p className="text-white/40 text-sm">No leads found. Launch a campaign to discover leads.</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 text-white/50 uppercase text-[10px] tracking-wider">
                  <tr>
                    <th className="px-4 py-3 font-medium">
                      <input
                        type="checkbox"
                        checked={leads.length > 0 && selectedLeadIds.length === leads.length}
                        onChange={toggleSelectAll}
                        className="accent-emerald-400"
                      />
                    </th>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Organization</th>
                    <th className="px-4 py-3 font-medium">Email</th>
                    <th className="px-4 py-3 font-medium">Phone</th>
                    <th className="px-4 py-3 font-medium">Role</th>
                    <th className="px-4 py-3 font-medium">Category</th>
                    <th className="px-4 py-3 font-medium">City</th>
                    <th className="px-4 py-3 font-medium">Source</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {leads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-white/5 transition-colors">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selectedLeadIds.includes(lead.id)}
                          onChange={() => toggleLeadSelection(lead.id)}
                          className="accent-emerald-400"
                        />
                      </td>
                      <td className="px-4 py-3 text-white font-medium">{lead.name || "—"}</td>
                      <td className="px-4 py-3 text-white/70">{lead.organization || "—"}</td>
                      <td className="px-4 py-3 text-white/70 text-xs">{lead.email || "—"}</td>
                      <td className="px-4 py-3 text-white/70 text-xs">{lead.phone || "—"}</td>
                      <td className="px-4 py-3 text-white/70 text-xs">{lead.role || "—"}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border ${
                          lead.category === 'Defence'
                            ? 'text-amber-400 bg-amber-400/10 border-amber-400/20'
                            : 'text-sky-400 bg-sky-400/10 border-sky-400/20'
                        }`}>
                          {lead.category || "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-white/70 text-xs">{lead.city || "—"}</td>
                      <td className="px-4 py-3 text-white/70 text-xs">{lead.source || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Upload Panel */}
      {activeTab === "upload" && (
        <div className="flex-1 animate-fade-in">
          <div className="mb-4">
            <h2 className="text-sm font-semibold text-white/80 uppercase tracking-wider">Upload Leads</h2>
            <p className="text-[11px] text-white/30">Upload a .csv or .xlsx file with lead data. Valid leads will appear in the Infos tab.</p>
          </div>
          <div className="mb-4 flex items-center gap-3">
            <input
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              className="text-sm text-white/70 file:mr-4 file:rounded-lg file:border-0 file:bg-sky-500/20 file:px-4 file:py-2 file:text-sm file:font-medium file:text-sky-300 hover:file:bg-sky-500/30"
            />
            <button
              onClick={handleUpload}
              disabled={!uploadFile || uploading}
              className={`rounded-lg px-4 py-2 text-xs font-bold text-white transition-colors ${!uploadFile || uploading ? "bg-white/5 border border-white/10 text-white/30 cursor-not-allowed" : "bg-amber-500/20 border border-amber-400/30 text-amber-300 hover:bg-amber-500/30"}`}
            >
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
          {uploadResult && (
            <div className="mb-4 rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-300">
              Uploaded: {uploadResult.inserted} inserted, {uploadResult.skipped} skipped.
              {uploadResult.inserted > 0 && (
                <button
                  onClick={() => setActiveTab("infos")}
                  className="ml-2 underline text-emerald-200 hover:text-white"
                >
                  Go to Infos →
                </button>
              )}
            </div>
          )}
          {uploadResult && uploadResult.leads.length > 0 && (
            <div className="overflow-x-auto rounded-xl border border-white/10">
              <table className="w-full text-left text-sm">
                <thead className="bg-white/5 text-white/50 uppercase text-[10px] tracking-wider">
                  <tr>
                    <th className="px-4 py-3 font-medium">Name</th>
                    <th className="px-4 py-3 font-medium">Email</th>
                    <th className="px-4 py-3 font-medium">Organization</th>
                    <th className="px-4 py-3 font-medium">City</th>
                    <th className="px-4 py-3 font-medium">Country</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {uploadResult.leads.map((lead: any, idx: number) => (
                    <tr key={idx} className="hover:bg-white/5 transition-colors">
                      <td className="px-4 py-3 text-white font-medium">{lead.name || "—"}</td>
                      <td className="px-4 py-3 text-white/70 text-xs">{lead.email || "—"}</td>
                      <td className="px-4 py-3 text-white/70 text-xs">{lead.organization || "—"}</td>
                      <td className="px-4 py-3 text-white/70 text-xs">{lead.city || "—"}</td>
                      <td className="px-4 py-3 text-white/70 text-xs">{lead.country || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
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
