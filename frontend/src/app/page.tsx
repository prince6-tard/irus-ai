"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import GlassCard from "@/components/GlassCard";
import ProductTile from "@/components/ProductTile";
import StepIndicator from "@/components/StepIndicator";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const STEPS = ["Domain", "Products", "Location", "Launch"];

interface Product {
  product_name: string;
  description: string;
  domain: string;
}

export default function Home() {
  const router = useRouter();

  const [currentStep, setCurrentStep] = useState(1);
  const [domain, setDomain] = useState<"Defence" | "Medical" | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [location, setLocation] = useState("");
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState("");

  // Fetch products on mount
  useEffect(() => {
    fetch(`${API_BASE}/products`)
      .then((res) => res.json())
      .then((data) => {
        if (data.status === "success") {
          setProducts(data.products || []);
        } else {
          setError(data.message || "Failed to load products");
        }
      })
      .catch((err) => setError(err.message || "Network error loading products"));
  }, []);

  const filteredProducts = products.filter(
    (p) => p.domain.toLowerCase() === domain?.toLowerCase()
  );

  const toggleProduct = (name: string) => {
    setSelectedProducts((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  };

  const handleLaunch = async () => {
    if (!domain || selectedProducts.length === 0 || !location.trim()) return;
    setLaunching(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/launch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain,
          locations: [location.trim()],
          selected_products: selectedProducts,
          dry_run: true,
        }),
      });
      const data = await res.json();
      if (data.status === "started" || data.status === "success") {
        router.push("/dashboard");
      } else {
        setError(data.message || "Launch failed");
        setLaunching(false);
      }
    } catch (err: any) {
      setError(err.message || "Network error launching campaign");
      setLaunching(false);
    }
  };

  return (
    <main className="relative min-h-screen flex flex-col items-center justify-start px-6 py-12">
      {/* Header */}
      <header className="text-center mb-8 animate-fade-in">
        <h1 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          IRUS AI Outreach
        </h1>
        <p className="mt-2 text-sm text-white/50 max-w-md mx-auto">
          Configure your outreach campaign in four simple steps.
        </p>
      </header>

      <StepIndicator steps={STEPS} currentStep={currentStep} />

      {/* Error banner */}
      {error && (
        <div className="mb-6 w-full max-w-xl rounded-lg border border-red-400/30 bg-red-400/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Step 1: Domain Selection */}
      {currentStep === 1 && (
        <div className="w-full max-w-3xl animate-fade-in">
          <h2 className="text-center text-lg font-semibold text-white/90 mb-6">
            Select your target domain
          </h2>
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">
            <GlassCard
              onClick={() => {
                setDomain("Defence");
                setSelectedProducts([]);
                setCurrentStep(2);
              }}
              strong
              className="flex flex-col items-center justify-center gap-4 py-14 hover:scale-[1.02]"
            >
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-sky-500/10 border border-sky-400/20">
                <svg className="h-8 w-8 text-sky-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
                </svg>
              </div>
              <div className="text-center">
                <h3 className="text-lg font-bold text-white">Defence</h3>
                <p className="mt-1 text-xs text-white/50 max-w-[16rem]">Drones, robots, anti-drone systems, simulators, tactical vehicles</p>
              </div>
            </GlassCard>

            <GlassCard
              onClick={() => {
                setDomain("Medical");
                setSelectedProducts([]);
                setCurrentStep(2);
              }}
              strong
              className="flex flex-col items-center justify-center gap-4 py-14 hover:scale-[1.02]"
            >
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10 border border-emerald-400/20">
                <svg className="h-8 w-8 text-emerald-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
                </svg>
              </div>
              <div className="text-center">
                <h3 className="text-lg font-bold text-white">Medical</h3>
                <p className="mt-1 text-xs text-white/50 max-w-[16rem]">Mobile clinics, ambulances, telemedicine, AR/VR simulators</p>
              </div>
            </GlassCard>
          </div>
        </div>
      )}

      {/* Step 2: Product Selection */}
      {currentStep === 2 && (
        <div className="w-full max-w-4xl animate-fade-in">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white/90">
              Select products for <span className="text-sky-300">{domain}</span>
            </h2>
            <span className="text-xs text-white/40">{selectedProducts.length} selected</span>
          </div>

          {filteredProducts.length === 0 ? (
            <div className="glass-card rounded-xl p-8 text-center">
              <p className="text-white/40 text-sm">No products loaded yet.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
              {filteredProducts.map((product) => (
                <ProductTile
                  key={product.product_name}
                  name={product.product_name}
                  description={product.description}
                  selected={selectedProducts.includes(product.product_name)}
                  onToggle={() => toggleProduct(product.product_name)}
                />
              ))}
            </div>
          )}

          <div className="mt-6 flex items-center justify-between">
            <button
              onClick={() => { setCurrentStep(1); setSelectedProducts([]); }}
              className="rounded-lg px-4 py-2 text-sm text-white/60 hover:text-white hover:bg-white/5 transition-colors"
            >
              ← Back
            </button>
            <button
              onClick={() => selectedProducts.length > 0 && setCurrentStep(3)}
              disabled={selectedProducts.length === 0}
              className={`glass-btn rounded-lg px-6 py-2.5 text-sm font-semibold text-white ${
                selectedProducts.length === 0 ? "opacity-40 cursor-not-allowed" : ""
              }`}
            >
              Confirm Selection →
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Location */}
      {currentStep === 3 && (
        <div className="w-full max-w-md animate-fade-in">
          <h2 className="text-center text-lg font-semibold text-white/90 mb-6">
            Where are you targeting?
          </h2>

          <GlassCard strong className="py-10 px-8">
            <label className="block text-xs font-medium uppercase tracking-wider text-white/50 mb-2">
              Target Geography
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="e.g., India, UAE, Singapore"
              className="glass-input w-full rounded-xl px-4 py-3 text-sm text-white placeholder-white/30"
            />
            <p className="mt-3 text-[11px] text-white/30">
              Apollo.io will search for leads in this location.
            </p>
          </GlassCard>

          <div className="mt-6 flex items-center justify-between">
            <button
              onClick={() => setCurrentStep(2)}
              className="rounded-lg px-4 py-2 text-sm text-white/60 hover:text-white hover:bg-white/5 transition-colors"
            >
              ← Back
            </button>
            <button
              onClick={() => location.trim() && setCurrentStep(4)}
              disabled={!location.trim()}
              className={`glass-btn rounded-lg px-6 py-2.5 text-sm font-semibold text-white ${
                !location.trim() ? "opacity-40 cursor-not-allowed" : ""
              }`}
            >
              Continue →
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Launch Confirmation */}
      {currentStep === 4 && (
        <div className="w-full max-w-lg animate-fade-in">
          <h2 className="text-center text-lg font-semibold text-white/90 mb-6">
            Ready to launch
          </h2>

          <GlassCard strong className="space-y-5">
            <div className="flex items-center justify-between border-b border-white/10 pb-3">
              <span className="text-xs uppercase tracking-wider text-white/40">Domain</span>
              <span className="text-sm font-semibold text-white">{domain}</span>
            </div>
            <div className="border-b border-white/10 pb-3">
              <span className="text-xs uppercase tracking-wider text-white/40 block mb-2">
                Selected Products ({selectedProducts.length})
              </span>
              <div className="flex flex-wrap gap-2">
                {selectedProducts.map((name) => (
                  <span
                    key={name}
                    className="inline-block rounded-md bg-sky-500/10 border border-sky-400/20 px-2.5 py-1 text-[11px] font-medium text-sky-300"
                  >
                    {name}
                  </span>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase tracking-wider text-white/40">Location</span>
              <span className="text-sm font-semibold text-white">{location}</span>
            </div>
          </GlassCard>

          <div className="mt-6 flex items-center justify-between">
            <button
              onClick={() => setCurrentStep(3)}
              className="rounded-lg px-4 py-2 text-sm text-white/60 hover:text-white hover:bg-white/5 transition-colors"
            >
              ← Back
            </button>
            <button
              onClick={handleLaunch}
              disabled={launching}
              className={`glass-btn rounded-lg px-8 py-2.5 text-sm font-bold text-white ${
                launching ? "opacity-60 cursor-wait" : ""
              }`}
            >
              {launching ? "Launching..." : "Launch Outreach →"}
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
