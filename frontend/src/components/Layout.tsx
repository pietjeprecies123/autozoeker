import clsx from "clsx";
import { useQuery } from "@tanstack/react-query";
import { Activity, BarChart3, Bell, Car, GitCompare, Heart, Loader2, Menu, Search, ShieldCheck, Sparkles, Wrench, X } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useApp, useProfile } from "../lib/store";
import { Button, Modal } from "./ui";

const NAV = [
  { to: "/", label: "Zoeken", icon: Search, end: true },
  { to: "/voor-jou", label: "Voor jou", icon: Sparkles },
  { to: "/favorieten", label: "Favorieten", icon: Heart },
  { to: "/zoekopdrachten", label: "Zoekopdrachten", icon: Bell },
  { to: "/markt", label: "Markt", icon: BarChart3 },
  { to: "/kenteken", label: "Kenteken", icon: ShieldCheck },
  { to: "/aandachtspunten", label: "Aandachtspunten", icon: Wrench },
  { to: "/status", label: "Status", icon: Activity },
];

function ProfilePicker() {
  const { meta, profileId, setProfileId } = useApp();
  const open = !!meta && meta.profiles.length > 0 && profileId == null;
  return (
    <Modal open={open} onClose={() => meta?.profiles[0] && setProfileId(meta.profiles[0].id)} title="Wie zoekt er?">
      <p className="mb-4 text-sm text-slate-600">Kies je profiel. Zoekopdrachten, meldingen en je voorkeuren worden per persoon bewaard; favorieten zijn gedeeld.</p>
      <div className="grid grid-cols-2 gap-3">
        {meta?.profiles.map((p) => (
          <button key={p.id} onClick={() => setProfileId(p.id)} className="rounded-xl border border-slate-200 p-5 text-lg font-semibold hover:border-brand-500 hover:bg-brand-50">
            {p.name}
          </button>
        ))}
      </div>
    </Modal>
  );
}

function CompareTray() {
  const { compare, clearCompare } = useApp();
  const navigate = useNavigate();
  if (compare.length === 0) return null;
  return (
    <div className="no-print fixed inset-x-0 bottom-0 z-40 border-t border-slate-200 bg-white/95 px-4 py-3 shadow-lg backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm">
          <GitCompare className="h-4 w-4 text-brand-700" />
          <span>{compare.length} auto{compare.length > 1 ? "'s" : ""} geselecteerd (max 4)</span>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={clearCompare}>Wissen</Button>
          <Button size="sm" onClick={() => navigate(`/vergelijk?ids=${compare.join(",")}`)} disabled={compare.length < 2}>
            Vergelijk
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { meta, profileId, setProfileId } = useApp();
  const profile = useProfile();
  const [mobileOpen, setMobileOpen] = useState(false);
  const alertsQ = useQuery({
    queryKey: ["alerts", profileId],
    queryFn: () => api.alerts(profileId!),
    enabled: !!profileId,
    refetchInterval: 60_000,
  });
  const unseen = alertsQ.data?.unseen ?? 0;

  return (
    <div className="min-h-screen pb-20">
      <header className="no-print sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-4 py-3">
          <Link to="/" className="flex items-center gap-2 font-bold text-slate-900">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-700 text-white"><Car className="h-5 w-5" /></span>
            Autozoeker
          </Link>
          <nav className="hidden flex-1 items-center gap-1 lg:flex">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  clsx("relative flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm", isActive ? "bg-brand-50 font-medium text-brand-800" : "text-slate-600 hover:bg-slate-100")
                }
              >
                <n.icon className="h-4 w-4" />
                {n.label}
                {n.to === "/voor-jou" && unseen > 0 && (
                  <span className="num ml-0.5 rounded-full bg-rose-600 px-1.5 text-[10px] font-semibold text-white">{unseen > 99 ? "99+" : unseen}</span>
                )}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            {meta && meta.profiles.length > 0 && (
              <div className="flex rounded-lg border border-slate-200 p-0.5 text-sm" role="group" aria-label="Profiel">
                {meta.profiles.map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setProfileId(p.id)}
                    className={clsx("rounded-md px-2.5 py-1", p.id === profile?.id ? "bg-brand-700 text-white" : "text-slate-600 hover:bg-slate-100")}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            )}
            <button className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden" onClick={() => setMobileOpen((o) => !o)} aria-label="Menu">
              {mobileOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>
        {mobileOpen && (
          <nav className="grid grid-cols-2 gap-1 border-t border-slate-200 px-4 py-3 lg:hidden">
            {NAV.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                onClick={() => setMobileOpen(false)}
                className={({ isActive }) => clsx("flex items-center gap-2 rounded-lg px-3 py-2 text-sm", isActive ? "bg-brand-50 text-brand-800" : "text-slate-700")}
              >
                <n.icon className="h-4 w-4" />
                {n.label}
                {n.to === "/voor-jou" && unseen > 0 && <span className="rounded-full bg-rose-600 px-1.5 text-[10px] text-white">{unseen}</span>}
              </NavLink>
            ))}
          </nav>
        )}
        {meta?.demo_mode && (
          <div className="border-t border-violet-200 bg-violet-50 px-4 py-1.5 text-center text-xs text-violet-800">
            Demo-modus: je ziet gegenereerde voorbeeldadvertenties (gemarkeerd met DEMO). Zet echte bronnen aan via <code>SOURCES</code> en <code>DEMO_MODE=false</code>.
          </div>
        )}
        {meta && !meta.ready && (
          <div className="flex items-center justify-center gap-2 border-t border-amber-200 bg-amber-50 px-4 py-1.5 text-xs text-amber-800">
            <Loader2 className="h-3 w-3 animate-spin" /> {meta.startup_message || "Bezig met opstarten…"}
          </div>
        )}
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{children}</main>
      <ProfilePicker />
      <CompareTray />
    </div>
  );
}
