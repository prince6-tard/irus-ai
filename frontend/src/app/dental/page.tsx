"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const DEFAULT_QUERIES = [
  "dental tourism to India from Canada",
  "dental tourism facilitator India Canada",
  "affordable dental implants India Canada facilitator",
  "dental tourism packages India Canada",
  "Indian dental clinic partner Canada",
  "dental implants abroad India Canada",
  "India dental tourism coordinator Canada",
  "medical tourism India dental Canada",
  "Indian dentist referral Canada",
  "cosmetic dentistry India Canada medical travel",
  "dental vacation India Canada",
  "dental travel agency India Canada",
  "international dental care India Canada",
  "Indian dental center partner Canada",
  "full mouth dental reconstruction India Canada",
  "Canada India dental travel coordinator",
  "dental medical tourism India Canada",
  "dental tourism facilitator sending patients India",
  "Canada to India dental treatment facilitator",
  "India dental tourism packages Canadian patients",
];

interface DentalLead {
  id: number;
  name: string;
  email: string;
  email_source: string;
  phone: string;
  organization: string;
  organization_domain: string;
  linkedin_url?: string;
  city: string;
  country: string;
  scrape_query: string;
  status: string;
  created_at: string;
}

interface DentalEmailLog {
  id: number;
  dental_lead_id: number;
  email: string;
  name: string;
  organization: string;
  city: string;
  country: string;
  status: string;
  sent_at: string;
}

export default function DentalPage() {
  const [leads, setLeads] = useState<DentalLead[]>([]);
  const [newLeads, setNewLeads] = useState<DentalLead[]>([]);
  const [logs, setLogs] = useState<DentalEmailLog[]>([]);
  const [activeTab, setActiveTab] = useState<"review" | "all" | "upload">("review");
  const [queries, setQueries] = useState<string[]>(DEFAULT_QUERIES);
  const [queryInput, setQueryInput] = useState("");
  const [scraping, setScraping] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<{ scraped: number; saved: number; skipped: number } | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [sending, setSending] = useState(false);
  const [sendResults, setSendResults] = useState<Record<number, string>>({});
  const [showConfirm, setShowConfirm] = useState(false);
  const [resendMode, setResendMode] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [uploadedLeads, setUploadedLeads] = useState<DentalLead[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");

  const fetchData = async () => {
    try {
      const [leadsRes, newRes, logsRes] = await Promise.all([
        fetch(`${API_BASE}/dental/leads`),
        fetch(`${API_BASE}/dental/leads?status=new`),
        fetch(`${API_BASE}/dental/log`),
      ]);
      const leadsData = await leadsRes.json();
      const newData = await newRes.json();
      const logsData = await logsRes.json();
      if (leadsData.status === "success") setLeads(leadsData.leads || []);
      if (newData.status === "success") setNewLeads(newData.leads || []);
      if (logsData.status === "success") setLogs(logsData.logs || []);
    } catch (err: any) {
      setError(err.message || "Failed to fetch data");
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    setSuccessMsg("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/dental/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      if (data.status === "success") {
        setSuccessMsg(`✓ ${data.inserted} leads uploaded, ${data.skipped} skipped`);
        setTimeout(() => setSuccessMsg(""), 4000);
        const leadsRes = await fetch(`${API_BASE}/dental/leads`);
        const leadsData = await leadsRes.json();
        if (leadsData.status === "success") {
          const allLeads = leadsData.leads || [];
          setLeads(allLeads);
          const uploadedEmails = new Set((data.leads || []).map((l: any) => l.email));
          setUploadedLeads(allLeads.filter((l: DentalLead) => uploadedEmails.has(l.email)));
        }
      } else {
        setError(data.message || "Upload failed");
      }
    } catch (err: any) {
      setError(err.message || "Upload error");
    }
    setUploading(false);
    if (e.target) e.target.value = "";
  };

  const addQuery = () => {
    const trimmed = queryInput.trim();
    if (trimmed && !queries.includes(trimmed)) {
      setQueries((prev) => [...prev, trimmed]);
    }
    setQueryInput("");
  };

  const removeQuery = (q: string) => {
    setQueries((prev) => prev.filter((x) => x !== q));
  };

  const handleScrape = async () => {
    if (queries.length === 0) return;
    setScraping(true);
    setError("");
    setScrapeResult(null);
    try {
      const res = await fetch(`${API_BASE}/dental/scrape`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ queries }),
      });
      const data = await res.json();
      if (data.status === "success" || data.status === "completed" || data.status === "ok") {
        setScrapeResult({
          scraped: data.scraped ?? 0,
          saved: data.saved ?? 0,
          skipped: data.skipped ?? 0,
        });
        setSuccessMsg(
          data.saved > 0
            ? `✓ ${data.saved} new leads found`
            : "⚠ 0 new leads — try different queries"
        );
        setTimeout(() => setSuccessMsg(""), 4000);
        await fetchData();
      } else {
        setError(data.message || "Scrape failed");
      }
    } catch (err: any) {
      setError(err.message || "Scrape error");
    }
    setScraping(false);
  };

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    const target = activeTab === "review" ? newLeads
      : activeTab === "upload" ? uploadedLeads
      : leads.filter((l) => l.status === "new" || l.status === "failed" || (resendMode && l.status === "sent"));
    if (selectedIds.length === target.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(target.map((l) => l.id));
    }
  };

  const handleSkipSelected = async () => {
    if (selectedIds.length === 0) return;
    setError("");
    try {
      const res = await fetch(`${API_BASE}/dental/leads/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lead_ids: selectedIds, status: "skipped" }),
      });
      const data = await res.json();
      if (data.status === "success") {
        setSuccessMsg(`Skipped ${selectedIds.length} lead(s)`);
        setTimeout(() => setSuccessMsg(""), 3000);
        setSelectedIds([]);
        await fetchData();
      } else {
        setError(data.message || "Failed to skip leads");
      }
    } catch (err: any) {
      setError(err.message || "Skip error");
    }
  };

  const handleSendSelected = async () => {
    if (selectedIds.length === 0) return;
    setShowConfirm(false);
    setSending(true);
    setError("");
    setSendResults({});
    try {
      const res = await fetch(`${API_BASE}/dental/send`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lead_ids: selectedIds }),
      });
      const data = await res.json();
      if (data.status === "success" || data.status === "completed") {
        const results: Record<number, string> = {};
        (data.results || []).forEach((r: any) => {
          results[r.lead_id] = r.status || "sent";
        });
        setSendResults(results);
        setSuccessMsg(
          `Sent: ${data.sent ?? 0} | Failed: ${data.failed ?? 0} | Skipped: ${data.skipped ?? 0}`
        );
        setTimeout(() => setSuccessMsg(""), 5000);
        setSelectedIds([]);
        await fetchData();
      } else {
        setError(data.message || "Send failed");
      }
    } catch (err: any) {
      setError(err.message || "Send error");
    }
    setSending(false);
  };

  const statusBadge = (status: string) => {
    const base = "inline-block rounded-md px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider border";
    switch (status) {
      case "new":
        return `${base} text-[#00E5CC] bg-[#00E5CC]/10 border-[#00E5CC]/20`;
      case "sent":
        return `${base} text-emerald-400 bg-emerald-400/10 border-emerald-400/20`;
      case "skipped":
        return `${base} text-white/40 bg-white/5 border-white/10`;
      case "failed":
        return `${base} text-red-400 bg-red-400/10 border-red-400/20`;
      default:
        return `${base} text-white/40 bg-white/5 border-white/10`;
    }
  };

  const selectableLeads = activeTab === "review"
    ? newLeads
    : activeTab === "upload"
    ? uploadedLeads
    : leads.filter((l) => l.status === "new" || l.status === "failed" || (resendMode && l.status === "sent"));

  return (
    <main className="relative min-h-screen flex flex-col px-6 py-10">
      {/* Header */}
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <Link
              href="/dashboard"
              className="text-sm text-white/40 hover:text-white/70 transition-colors"
            >
              ← Back to Dashboard
            </Link>
          </div>
          <h1 className="text-2xl font-bold text-white tracking-tight">Dental Connect</h1>
          <p className="mt-1 text-sm text-white/50">Global Dental Tourism Outreach</p>
        </div>
        {leads.length > 0 && (
          <span className="self-start sm:self-auto rounded-full bg-[#00E5CC]/10 border border-[#00E5CC]/20 px-3 py-1 text-xs font-medium text-[#00E5CC]">
            {leads.length} total leads
          </span>
        )}
      </header>

      {/* Error banner */}
      {error && (
        <div className="mb-6 w-full rounded-lg border border-red-400/30 bg-red-400/10 px-4 py-3 text-sm text-red-300 animate-fade-in">
          {error}
          <button
            onClick={() => setError("")}
            className="ml-3 underline text-red-200 hover:text-white"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Success banner */}
      {successMsg && (
        <div className="mb-6 w-full rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-300 animate-fade-in">
          {successMsg}
        </div>
      )}

      {/* Scrape section */}
      <div className="glass-card rounded-xl p-5 mb-6 border-[#00E5CC]/20">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
          <div>
            <h2 className="text-sm font-semibold text-white/80 uppercase tracking-wider">Scrape Medical Tourism Facilitators</h2>
            <p className="text-[11px] text-white/30 mt-0.5">Add search queries to find Canadian facilitators who refer patients internationally</p>
          </div>
          <button
            onClick={handleScrape}
            disabled={scraping || queries.length === 0}
            className={`shrink-0 rounded-lg px-5 py-2 text-sm font-bold text-white transition-all ${
              scraping || queries.length === 0
                ? "bg-white/5 border border-white/10 text-white/30 cursor-not-allowed"
                : "bg-[#00E5CC]/20 border border-[#00E5CC]/30 text-[#00E5CC] hover:bg-[#00E5CC]/30"
            }`}
          >
            {scraping ? (
              <span className="flex items-center gap-2">
                <span className="relative flex h-3 w-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[#00E5CC] opacity-75"></span>
                  <span className="relative inline-flex h-3 w-3 rounded-full bg-[#00E5CC]"></span>
                </span>
                Scraping facilitators...
              </span>
            ) : (
              "Run Scrape"
            )}
          </button>
        </div>

        {/* Scrape result */}
        {scrapeResult && (
          <div className={`mb-4 rounded-lg px-4 py-2 text-sm border animate-fade-in ${
            scrapeResult.saved > 0
              ? "border-[#00E5CC]/30 bg-[#00E5CC]/10 text-[#00E5CC]"
              : "border-white/10 bg-white/5 text-white/50"
          }`}>
            Scraper: {scrapeResult.scraped} found, {scrapeResult.saved} saved, {scrapeResult.skipped} skipped
          </div>
        )}

        {/* Query chips */}
        <div className="flex flex-wrap gap-2 mb-3">
          {queries.map((q) => (
            <span
              key={q}
              className="inline-flex items-center gap-1.5 rounded-full bg-[#00E5CC]/10 border border-[#00E5CC]/20 px-3 py-1 text-xs font-medium text-[#00E5CC]"
            >
              {q}
              <button
                onClick={() => removeQuery(q)}
                className="ml-0.5 text-[#00E5CC]/60 hover:text-[#00E5CC] transition-colors"
                aria-label={`Remove ${q}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>

        {/* Query input */}
        <div className="flex gap-2">
          <input
            type="text"
            value={queryInput}
            onChange={(e) => setQueryInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                addQuery();
              }
            }}
            placeholder="Add a search query and press Enter..."
            className="glass-input flex-1 rounded-lg px-3 py-2 text-sm text-white placeholder-white/30"
          />
          <button
            onClick={addQuery}
            className="rounded-lg bg-white/5 border border-white/10 px-4 py-2 text-sm font-medium text-white/60 hover:text-white hover:bg-white/10 transition-colors"
          >
            Add
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 mb-4 border-b border-white/10 pb-2">
        <button
          onClick={() => { setActiveTab("review"); setSelectedIds([]); setSendResults({}); }}
          className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${
            activeTab === "review"
              ? "bg-[#00E5CC]/20 text-[#00E5CC] border border-[#00E5CC]/20"
              : "text-white/60 hover:text-white hover:bg-white/5"
          }`}
        >
          Review &amp; Send {newLeads.length > 0 && (
            <span className="ml-1 text-[10px] bg-[#00E5CC]/20 px-1.5 py-0.5 rounded-full">{newLeads.length}</span>
          )}
        </button>
        <button
          onClick={() => { setActiveTab("upload"); setSelectedIds([]); setSendResults({}); setUploadedLeads([]); }}
          className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${
            activeTab === "upload"
              ? "bg-amber-400/20 text-amber-400 border border-amber-400/20"
              : "text-white/60 hover:text-white hover:bg-white/5"
          }`}
        >
          Upload CSV
        </button>
        <button
          onClick={() => { setActiveTab("all"); setSelectedIds([]); setSendResults({}); }}
          className={`text-sm font-medium px-3 py-1.5 rounded-lg transition-colors ${
            activeTab === "all"
              ? "bg-white/10 text-white border border-white/20"
              : "text-white/60 hover:text-white hover:bg-white/5"
          }`}
        >
          All Scraped Leads {leads.length > 0 && (
            <span className="ml-1 text-[10px] bg-white/10 px-1.5 py-0.5 rounded-full">{leads.length}</span>
          )}
        </button>
      </div>

      {/* Review & Send tab */}
      {activeTab === "review" && (
        <div className="flex-1 animate-fade-in">
          {newLeads.length === 0 ? (
            <div className="glass-card rounded-xl p-10 text-center">
              <p className="text-white/40 text-sm">No new leads to review. Run a scrape to find facilitators.</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-xs text-white/50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedIds.length === newLeads.length && newLeads.length > 0}
                      onChange={toggleSelectAll}
                      className="accent-[#00E5CC]"
                    />
                    Select All
                  </label>
                  {selectedIds.length > 0 && (
                    <span className="text-xs text-white/40">{selectedIds.length} selected</span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSkipSelected}
                    disabled={selectedIds.length === 0}
                    className={`rounded-lg px-4 py-2 text-xs font-medium text-white transition-colors ${
                      selectedIds.length === 0
                        ? "bg-white/5 border border-white/10 text-white/30 cursor-not-allowed"
                        : "bg-white/5 border border-white/10 hover:bg-white/10 text-white/70"
                    }`}
                  >
                    Skip Selected
                  </button>
                  <button
                    onClick={() => setShowConfirm(true)}
                    disabled={selectedIds.length === 0}
                    className={`rounded-lg px-4 py-2 text-xs font-bold text-white transition-all ${
                      selectedIds.length === 0
                        ? "bg-white/5 border border-white/10 text-white/30 cursor-not-allowed"
                        : "bg-[#00E5CC]/20 border border-[#00E5CC]/30 text-[#00E5CC] hover:bg-[#00E5CC]/30"
                    }`}
                  >
                    Send Selected ({selectedIds.length})
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto rounded-xl border border-white/10">
                <table className="w-full text-left text-sm">
                  <thead className="bg-white/5 text-white/50 uppercase text-[10px] tracking-wider">
                    <tr>
                      <th className="px-4 py-3 font-medium w-8"></th>
                      <th className="px-4 py-3 font-medium">Organization</th>
                      <th className="px-4 py-3 font-medium">Email</th>
                      <th className="px-4 py-3 font-medium">LinkedIn</th>
                      <th className="px-4 py-3 font-medium">City</th>
                      <th className="px-4 py-3 font-medium">Country</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {newLeads.map((lead) => (
                      <tr key={lead.id} className="hover:bg-white/5 transition-colors">
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(lead.id)}
                            onChange={() => toggleSelect(lead.id)}
                            className="accent-[#00E5CC]"
                          />
                        </td>
                        <td className="px-4 py-3 text-white font-medium">{lead.organization || "—"}</td>
                        <td className="px-4 py-3 text-white/70 text-xs">{lead.email || "—"}</td>
                        <td className="px-4 py-3 text-white/70 text-xs max-w-[200px] truncate">
                          {lead.linkedin_url ? (
                            <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" title={lead.linkedin_url}>
                              {lead.linkedin_url}
                            </a>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-3 text-white/70 text-xs">{lead.city || "—"}</td>
                        <td className="px-4 py-3 text-white/70 text-xs">{lead.country || "—"}</td>
                        <td className="px-4 py-3">
                          {sendResults[lead.id] ? (
                            <span className={`text-xs font-medium ${
                              sendResults[lead.id] === "sent" ? "text-emerald-400" : "text-red-400"
                            }`}>
                              {sendResults[lead.id] === "sent" ? "✓ sent" : "✗ failed"}
                            </span>
                          ) : (
                            <span className={statusBadge(lead.status)}>{lead.status}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* Upload CSV tab */}
      {activeTab === "upload" && (
        <div className="flex-1 animate-fade-in">
          {/* Upload area */}
          <div className="glass-card rounded-xl p-6 mb-6 border border-amber-400/20">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold text-white/80 uppercase tracking-wider">
                  Upload CSV or Excel
                </h2>
                <p className="text-[11px] text-white/30 mt-0.5">
                  Upload a file with travel agency emails to send collaboration emails
                </p>
              </div>
              <label
                className={`shrink-0 cursor-pointer rounded-lg px-5 py-2 text-sm font-bold text-white transition-all ${
                  uploading
                    ? "bg-white/5 border border-white/10 text-white/30 cursor-wait"
                    : "bg-amber-400/20 border border-amber-400/30 text-amber-400 hover:bg-amber-400/30"
                }`}
              >
                {uploading ? (
                  <span className="flex items-center gap-2">
                    <span className="relative flex h-3 w-3">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75"></span>
                      <span className="relative inline-flex h-3 w-3 rounded-full bg-amber-400"></span>
                    </span>
                    Uploading...
                  </span>
                ) : (
                  "Choose File"
                )}
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls"
                  onChange={handleUpload}
                  disabled={uploading}
                  className="hidden"
                />
              </label>
            </div>
            <p className="mt-3 text-[11px] text-white/20">
              Supported formats: .csv, .xlsx, .xls — columns like Email, Name, Organization, City, Country
            </p>
          </div>

          {/* Uploaded leads table */}
          {uploadedLeads.length === 0 ? (
            <div className="glass-card rounded-xl p-10 text-center">
              <p className="text-white/40 text-sm">
                No leads uploaded yet. Select a CSV or Excel file above to get started.
              </p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-xs text-white/50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedIds.length === uploadedLeads.length && uploadedLeads.length > 0}
                      onChange={toggleSelectAll}
                      className="accent-amber-400"
                    />
                    Select All
                  </label>
                  {selectedIds.length > 0 && (
                    <span className="text-xs text-white/40">{selectedIds.length} selected</span>
                  )}
                </div>
                <button
                  onClick={() => setShowConfirm(true)}
                  disabled={selectedIds.length === 0}
                  className={`rounded-lg px-4 py-2 text-xs font-bold text-white transition-all ${
                    selectedIds.length === 0
                      ? "bg-white/5 border border-white/10 text-white/30 cursor-not-allowed"
                      : "bg-[#00E5CC]/20 border border-[#00E5CC]/30 text-[#00E5CC] hover:bg-[#00E5CC]/30"
                  }`}
                >
                  Send Selected ({selectedIds.length})
                </button>
              </div>

              <div className="overflow-x-auto rounded-xl border border-white/10">
                <table className="w-full text-left text-sm">
                  <thead className="bg-white/5 text-white/50 uppercase text-[10px] tracking-wider">
                    <tr>
                      <th className="px-4 py-3 font-medium w-8"></th>
                      <th className="px-4 py-3 font-medium">Organization</th>
                      <th className="px-4 py-3 font-medium">Email</th>
                      <th className="px-4 py-3 font-medium">LinkedIn</th>
                      <th className="px-4 py-3 font-medium">City</th>
                      <th className="px-4 py-3 font-medium">Country</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {uploadedLeads.map((lead) => (
                      <tr key={lead.id} className="hover:bg-white/5 transition-colors">
                        <td className="px-4 py-3">
                          <input
                            type="checkbox"
                            checked={selectedIds.includes(lead.id)}
                            onChange={() => toggleSelect(lead.id)}
                            className="accent-amber-400"
                          />
                        </td>
                        <td className="px-4 py-3 text-white font-medium">{lead.organization || "—"}</td>
                        <td className="px-4 py-3 text-white/70 text-xs">{lead.email || "—"}</td>
                        <td className="px-4 py-3 text-white/70 text-xs max-w-[200px] truncate">
                          {lead.linkedin_url ? (
                            <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" title={lead.linkedin_url}>
                              {lead.linkedin_url}
                            </a>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-3 text-white/70 text-xs">{lead.city || "—"}</td>
                        <td className="px-4 py-3 text-white/70 text-xs">{lead.country || "—"}</td>
                        <td className="px-4 py-3">
                          {sendResults[lead.id] ? (
                            <span className={`text-xs font-medium ${
                              sendResults[lead.id] === "sent" ? "text-emerald-400" : "text-red-400"
                            }`}>
                              {sendResults[lead.id] === "sent" ? "✓ sent" : "✗ failed"}
                            </span>
                          ) : (
                            <span className={statusBadge(lead.status)}>{lead.status}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      )}

      {/* All Leads tab */}
      {activeTab === "all" && (
        <div className="flex-1 animate-fade-in">
          {leads.length === 0 ? (
            <div className="glass-card rounded-xl p-10 text-center">
              <p className="text-white/40 text-sm">No leads scraped yet. Run a scrape to get started.</p>
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <label className="flex items-center gap-2 text-xs text-white/50 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={selectedIds.length === selectableLeads.length && selectableLeads.length > 0}
                      onChange={toggleSelectAll}
                      className="accent-[#00E5CC]"
                    />
                    Select All
                  </label>
                  {selectedIds.length > 0 && (
                    <span className="text-xs text-white/40">{selectedIds.length} selected</span>
                  )}
                </div>
                <label className="flex items-center gap-2 text-xs text-white/60 cursor-pointer ml-4">
                  <div
                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${resendMode ? 'bg-[#00E5CC]' : 'bg-white/20'}`}
                    onClick={() => { setResendMode(v => !v); setSelectedIds([]); }}
                  >
                    <span className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${resendMode ? 'translate-x-5' : 'translate-x-1'}`} />
                  </div>
                  Resend Mode
                </label>
                {selectedIds.length > 0 && (
                  <button
                    onClick={() => setShowConfirm(true)}
                    className="rounded-lg px-4 py-2 text-xs font-bold text-white bg-[#00E5CC]/20 border border-[#00E5CC]/30 text-[#00E5CC] hover:bg-[#00E5CC]/30 transition-all"
                  >
                    Send Selected ({selectedIds.length})
                  </button>
                )}
              </div>

              <div className="overflow-x-auto rounded-xl border border-white/10">
                <table className="w-full text-left text-sm">
                  <thead className="bg-white/5 text-white/50 uppercase text-[10px] tracking-wider">
                    <tr>
                      <th className="px-4 py-3 font-medium w-8"></th>
                      <th className="px-4 py-3 font-medium">Organization</th>
                      <th className="px-4 py-3 font-medium">Email</th>
                      <th className="px-4 py-3 font-medium">LinkedIn</th>
                      <th className="px-4 py-3 font-medium">City</th>
                      <th className="px-4 py-3 font-medium">Country</th>
                      <th className="px-4 py-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {leads.map((lead) => {
                      const isSelectable = lead.status === "new" || lead.status === "failed" || (resendMode && lead.status === "sent");
                      return (
                        <tr key={lead.id} className="hover:bg-white/5 transition-colors">
                          <td className="px-4 py-3">
                            {isSelectable ? (
                              <input
                                type="checkbox"
                                checked={selectedIds.includes(lead.id)}
                                onChange={() => toggleSelect(lead.id)}
                                className="accent-[#00E5CC]"
                              />
                            ) : (
                              <span className="inline-block w-3.5 h-3.5" />
                            )}
                          </td>
                          <td className="px-4 py-3 text-white font-medium">
                            {lead.organization || "—"}
                            {lead.status === "failed" && (
                              <button
                                onClick={async () => {
                                  setSelectedIds([lead.id]);
                                  setShowConfirm(true);
                                }}
                                className="ml-2 text-[10px] text-red-400 hover:text-red-300 underline"
                                title="Resend"
                              >
                                ↻
                              </button>
                            )}
                          </td>
                          <td className="px-4 py-3 text-white/70 text-xs">{lead.email || "—"}</td>
                        <td className="px-4 py-3 text-white/70 text-xs max-w-[200px] truncate">
                          {lead.linkedin_url ? (
                            <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer" title={lead.linkedin_url}>
                              {lead.linkedin_url}
                            </a>
                          ) : "—"}
                        </td>
                        <td className="px-4 py-3 text-white/70 text-xs">{lead.city || "—"}</td>
                        <td className="px-4 py-3 text-white/70 text-xs">{lead.country || "—"}</td>
                        <td className="px-4 py-3">
                          {sendResults[lead.id] ? (
                            <span className={`text-xs font-medium ${
                              sendResults[lead.id] === "sent" ? "text-emerald-400" : "text-red-400"
                            }`}>
                              {sendResults[lead.id] === "sent" ? "✓ sent" : "✗ failed"}
                            </span>
                          ) : (
                            <span className={statusBadge(lead.status)}>{lead.status}</span>
                          )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Email Send Log */}
              <div className="mt-6">
                <button
                  onClick={() => setShowLog((prev) => !prev)}
                  className="flex items-center gap-2 text-sm font-semibold text-white/80 uppercase tracking-wider mb-3 hover:text-white transition-colors"
                >
                  <span className={`transform transition-transform ${showLog ? "rotate-90" : ""}`}>▶</span>
                  Email Send Log ({logs.length})
                </button>

                {showLog && (
                  <div className="animate-fade-in">
                    {logs.length === 0 ? (
                      <div className="glass-card rounded-xl p-6 text-center">
                        <p className="text-white/40 text-sm">No emails sent yet.</p>
                      </div>
                    ) : (
                      <div className="overflow-x-auto rounded-xl border border-white/10">
                        <table className="w-full text-left text-sm">
                          <thead className="bg-white/5 text-white/50 uppercase text-[10px] tracking-wider">
                            <tr>
                              <th className="px-4 py-3 font-medium">Sent At</th>
                              <th className="px-4 py-3 font-medium">Organization</th>
                              <th className="px-4 py-3 font-medium">Email</th>
                              <th className="px-4 py-3 font-medium">City</th>
                              <th className="px-4 py-3 font-medium">Country</th>
                              <th className="px-4 py-3 font-medium">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/5">
                            {logs.map((log) => (
                              <tr key={log.id} className="hover:bg-white/5 transition-colors">
                                <td className="px-4 py-3 text-white/50 text-xs">
                                  {log.sent_at ? new Date(log.sent_at).toLocaleString() : "—"}
                                </td>
                                <td className="px-4 py-3 text-white font-medium">{log.organization || "—"}</td>
                                <td className="px-4 py-3 text-white/70 text-xs">{log.email || "—"}</td>
                                <td className="px-4 py-3 text-white/70 text-xs">{log.city || "—"}</td>
                                <td className="px-4 py-3 text-white/70 text-xs">{log.country || "—"}</td>
                                <td className="px-4 py-3">
                                  <span className={`text-xs font-medium ${
                                    log.status === "sent" ? "text-emerald-400" : "text-red-400"
                                  }`}>
                                    {log.status}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Confirmation modal */}
      {showConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
          <div className="glass-strong w-full max-w-md rounded-2xl p-6 space-y-5">
            <div>
              <h3 className="text-lg font-bold text-white">Confirm Send</h3>
              <p className="mt-2 text-sm text-white/60">
                You are about to send the Dr. Swati Singhal collaboration email to{" "}
                <span className="text-[#00E5CC] font-semibold">{selectedIds.length}</span> recipient
                {selectedIds.length !== 1 ? "s" : ""}. Confirm?
              </p>
            </div>
            <div className="flex items-center justify-end gap-3">
              <button
                onClick={() => setShowConfirm(false)}
                className="rounded-lg bg-white/5 border border-white/10 px-5 py-2 text-sm font-medium text-white/60 hover:text-white hover:bg-white/10 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleSendSelected}
                disabled={sending}
                className={`rounded-lg px-5 py-2 text-sm font-bold text-white transition-all ${
                  sending
                    ? "bg-white/5 border border-white/10 text-white/30 cursor-wait"
                    : "bg-[#00E5CC]/20 border border-[#00E5CC]/30 text-[#00E5CC] hover:bg-[#00E5CC]/30"
                }`}
              >
                {sending ? "Sending..." : "Confirm & Send"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}