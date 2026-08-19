"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

export default function Navbar() {
  const { user, logout, loading } = useAuth();
  const [showSettings, setShowSettings] = useState(false);

  const isPaid = user && user.plan !== "free";

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="container-page flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-semibold text-slate-900">
          <span className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 text-sm text-white">AI</span>
          <span>Data Profiler</span>
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-slate-600 md:flex">
          {!user && (
            <>
              <Link href="/#features" className="hover:text-slate-900">Features</Link>
              <Link href="/#pricing" className="hover:text-slate-900">Pricing</Link>
              <Link href="/#faq" className="hover:text-slate-900">FAQ</Link>
            </>
          )}
        </nav>
        <div className="flex items-center gap-3">
          {loading ? null : user ? (
            <>
              <Link href="/dashboard" className="text-sm text-slate-600 hover:text-slate-900">Dashboard</Link>
              <Link href="/compare" className="text-sm text-slate-600 hover:text-slate-900">Compare</Link>

              {/* Settings dropdown */}
              <div className="relative">
                <button onClick={() => setShowSettings(!showSettings)}
                  className="text-sm text-slate-600 hover:text-slate-900 flex items-center gap-1">
                  Settings
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </button>
                {showSettings && (
                  <div className="absolute right-0 mt-2 w-52 rounded-lg border border-slate-200 bg-white py-1 shadow-lg z-50"
                    onMouseLeave={() => setShowSettings(false)}>
                    {isPaid && (
                      <>
                        <Link href="/settings/connectors" className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Database Connectors</Link>
                        <Link href="/settings/schedules" className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Scheduled Analysis</Link>
                        <Link href="/settings/rules" className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Quality Rules</Link>
                        <Link href="/settings/webhooks" className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Webhooks</Link>
                        <Link href="/settings/audit" className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Audit Trail</Link>
                      </>
                    )}
                    {user.plan === "team" && (
                      <>
                        <div className="border-t border-slate-100 my-1" />
                        <Link href="/settings/team" className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">Team</Link>
                        <Link href="/settings/api-keys" className="block px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">API Keys</Link>
                      </>
                    )}
                    {user.plan === "free" && (
                      <p className="px-4 py-2 text-xs text-slate-400">Upgrade for more settings</p>
                    )}
                  </div>
                )}
              </div>

              {user.avatar_url ? (
                <img src={user.avatar_url} alt="" className="h-7 w-7 rounded-full" />
              ) : null}
              <button onClick={logout} className="btn-primary">Log out</button>
            </>
          ) : (
            <>
              <Link href="/login" className="btn-secondary">Log in</Link>
              <Link href="/register" className="btn-primary">Analyze Your Dataset</Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
