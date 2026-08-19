import Link from "next/link";
import Navbar from "@/components/Navbar";

const FEATURES = [
  { title: "Missing value analysis", desc: "Severity-graded (LOW/MEDIUM/HIGH/CRITICAL) breakdown per column with imputation suggestions." },
  { title: "Duplicate detection", desc: "Finds exact duplicate rows and duplicated identifier candidates." },
  { title: "Outlier detection", desc: "IQR and Z-score methods report outliers without silently deleting data." },
  { title: "Correlation analysis", desc: "Pearson and Spearman correlations with a configurable high-correlation threshold." },
  { title: "Target & leakage detection", desc: "Heuristically suggests a target column and flags potential data leakage — never asserted as fact." },
  { title: "ML Readiness Score", desc: "A transparent 0-100 score with a full breakdown, not a black box." },
];

const PRICING = [
  {
    name: "Free", price: "₹0", period: "forever",
    features: ["3 analyses / month", "Basic profiling & data quality report", "Web report viewer", "CSV issue export"],
    cta: "Start Free", href: "/register",
  },
  {
    name: "Pro", price: "₹499", period: "/ month", highlighted: true,
    features: ["50 analyses / month", "Larger datasets", "AI-generated insights", "Advanced statistics", "PDF export", "Python cleaning snippets"],
    cta: "Go Pro", href: "/register",
  },
  {
    name: "Team", price: "₹1,999", period: "/ month",
    features: ["500 analyses / month", "Multiple users", "Shared reports", "API access", "Priority processing"],
    cta: "Contact Sales", href: "/register",
  },
];

const FAQ = [
  { q: "What file formats are supported?", a: "CSV and Excel (.xlsx). We validate file structure, size and content before analysis — not just the file extension." },
  { q: "Is my data sent to the LLM?", a: "No. Only aggregated statistics and detected issues are sent to the AI model for generating plain-language insights — never your raw dataset or individual cell values." },
  { q: "How is the ML Readiness Score calculated?", a: "It's a transparent, weighted heuristic covering data quality, feature quality, target quality, distribution quality, and leakage risk. It's a readiness guideline, not a model performance prediction." },
  { q: "How long is my uploaded file kept?", a: "Uploaded files are deleted immediately after processing. Only the derived statistical report is stored in your account." },
];

export default function LandingPage() {
  return (
    <main>
      <Navbar />

      <section className="border-b border-slate-200 bg-white">
        <div className="container-page grid gap-10 py-20 md:grid-cols-2 md:items-center">
          <div>
            <h1 className="text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
              Understand Your Dataset Before You Build Your Model.
            </h1>
            <p className="mt-5 text-lg text-slate-600">
              Upload a CSV or Excel file and automatically discover data-quality problems,
              statistical patterns, ML-readiness issues, and actionable recommendations.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/register" className="btn-primary px-6 py-3 text-base">Analyze Your Dataset</Link>
              <Link href="#how-it-works" className="btn-secondary px-6 py-3 text-base">See How It Works</Link>
            </div>
            <p className="mt-4 text-xs text-slate-500">No credit card required for the Free plan.</p>
          </div>
          <div className="card p-6">
            <div className="mb-4 flex items-center justify-between">
              <span className="text-sm font-medium text-slate-700">customers.csv</span>
              <span className="badge bg-green-100 text-green-800">Analysis Complete</span>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="rounded-lg bg-slate-50 p-4 text-center">
                <div className="text-2xl font-bold text-brand-600">82</div>
                <div className="text-xs text-slate-500">ML Readiness Score</div>
              </div>
              <div className="rounded-lg bg-slate-50 p-4 text-center">
                <div className="text-2xl font-bold text-slate-900">7</div>
                <div className="text-xs text-slate-500">Issues Detected</div>
              </div>
            </div>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex items-center justify-between rounded-md bg-red-50 px-3 py-2">
                <span className="text-red-800">4.3% missing values in `income`</span>
                <span className="badge bg-red-100 text-red-800">HIGH</span>
              </div>
              <div className="flex items-center justify-between rounded-md bg-amber-50 px-3 py-2">
                <span className="text-amber-800">Inconsistent categories in `gender`</span>
                <span className="badge bg-amber-100 text-amber-800">MEDIUM</span>
              </div>
              <div className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2">
                <span className="text-slate-700">`customer_id` looks like an ID column</span>
                <span className="badge bg-slate-200 text-slate-700">LOW</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="features" className="py-20">
        <div className="container-page">
          <h2 className="text-2xl font-semibold text-slate-900">Everything you need to trust your data</h2>
          <p className="mt-2 max-w-2xl text-slate-600">
            A single upload runs a full deterministic analysis pipeline, then an AI layer explains it in plain language.
          </p>
          <div className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {FEATURES.map((f) => (
              <div key={f.title} className="card p-5">
                <h3 className="font-medium text-slate-900">{f.title}</h3>
                <p className="mt-2 text-sm text-slate-600">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="border-y border-slate-200 bg-white py-20">
        <div className="container-page">
          <h2 className="text-2xl font-semibold text-slate-900">How it works</h2>
          <div className="mt-10 grid gap-6 md:grid-cols-4">
            {[
              ["1", "Upload", "Upload a CSV or Excel file up to your plan's size limit."],
              ["2", "Automated profiling", "We compute statistics, detect quality issues, correlations, and target candidates."],
              ["3", "AI insights", "An LLM turns the deterministic analysis into a plain-language report — never inventing numbers."],
              ["4", "Download & act", "Export as PDF, JSON, or a CSV of issues, with concrete cleaning code snippets."],
            ].map(([n, t, d]) => (
              <div key={n}>
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-600 text-sm font-semibold text-white">{n}</div>
                <h3 className="mt-3 font-medium text-slate-900">{t}</h3>
                <p className="mt-1 text-sm text-slate-600">{d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="pricing" className="py-20">
        <div className="container-page">
          <h2 className="text-2xl font-semibold text-slate-900">Simple, transparent pricing</h2>
          <p className="mt-2 text-slate-600">Start free. Upgrade when you need more analyses or AI-powered reports.</p>
          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {PRICING.map((p) => (
              <div key={p.name} className={`card p-6 ${p.highlighted ? "border-brand-500 ring-1 ring-brand-500" : ""}`}>
                {p.highlighted && <div className="mb-3 badge bg-brand-100 text-brand-700">Most popular</div>}
                <h3 className="text-lg font-semibold text-slate-900">{p.name}</h3>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="text-3xl font-bold text-slate-900">{p.price}</span>
                  <span className="text-sm text-slate-500">{p.period}</span>
                </div>
                <ul className="mt-5 space-y-2 text-sm text-slate-600">
                  {p.features.map((f) => (
                    <li key={f} className="flex gap-2">
                      <span className="text-brand-600">✓</span>{f}
                    </li>
                  ))}
                </ul>
                <Link href={p.href} className={`mt-6 block text-center ${p.highlighted ? "btn-primary" : "btn-secondary"}`}>
                  {p.cta}
                </Link>
              </div>
            ))}
          </div>
          <p className="mt-4 text-xs text-slate-500">
            Prices shown in INR. Billing is processed via Stripe; Razorpay support for Indian customers is planned.
          </p>
        </div>
      </section>

      <section id="faq" className="border-t border-slate-200 bg-white py-20">
        <div className="container-page max-w-3xl">
          <h2 className="text-2xl font-semibold text-slate-900">Frequently asked questions</h2>
          <div className="mt-8 space-y-6">
            {FAQ.map((item) => (
              <div key={item.q}>
                <h3 className="font-medium text-slate-900">{item.q}</h3>
                <p className="mt-1 text-sm text-slate-600">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="border-t border-slate-200 py-10">
        <div className="container-page flex flex-col items-center justify-between gap-4 text-sm text-slate-500 md:flex-row">
          <span>© {new Date().getFullYear()} AI Data Profiler. All rights reserved.</span>
          <div className="flex gap-6">
            <Link href="/privacy" className="hover:text-slate-800">Privacy Policy</Link>
            <Link href="/login" className="hover:text-slate-800">Log in</Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
