import { useState } from "react";
import { ChevronDown, ExternalLink, HelpCircle, Search, ShieldCheck, ShieldAlert, Car } from "lucide-react";
import clsx from "clsx";
import { euro } from "../lib/format";
import type { Issue } from "../lib/types";
import { Badge, severityTone } from "./ui";

const FIX_LABEL: Record<string, string> = {
  recall: "Terugroepactie",
  campaign: "Servicecampagne",
  revised_part: "Verbeterd onderdeel",
  software: "Software-update",
  warranty_extension: "Garantieverlenging",
  maintenance: "Onderhoud",
  none: "Geen structurele oplossing",
};
const CERTAINTY: Record<string, string> = {
  zeker: "Geldt voor deze auto",
  waarschijnlijk: "Waarschijnlijk van toepassing",
  mogelijk: "Mogelijk van toepassing (motor/bouwjaar onbekend)",
};

export default function IssueCard({ issue, defaultOpen = false }: { issue: Issue; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-lg border border-slate-200">
      <button className="flex w-full items-start gap-3 p-3 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <Badge tone={severityTone(issue.severity)} className="mt-0.5 shrink-0">{issue.severity_label ?? issue.severity}</Badge>
        <div className="min-w-0 flex-1">
          <div className="font-medium text-slate-900">{issue.title}</div>
          <div className="mt-1 flex flex-wrap gap-1.5">
            {issue.certainty && <span className="text-xs text-slate-500">{CERTAINTY[issue.certainty]}</span>}
            {issue.recall_status === "hersteld" && <Badge tone="good"><ShieldCheck className="h-3 w-3" />Recall uitgevoerd (RDW)</Badge>}
            {issue.recall_status === "open" && <Badge tone="bad"><ShieldAlert className="h-3 w-3" />Recall nog open (RDW)</Badge>}
            {issue.repair_cost_eur && <Badge tone="ok">{euro(issue.repair_cost_eur[0])}–{euro(issue.repair_cost_eur[1])}</Badge>}
            {issue.likelihood && <Badge tone="ok">komt {issue.likelihood === "high" ? "vaak" : issue.likelihood === "medium" ? "regelmatig" : "soms"} voor</Badge>}
            {issue.ai && <Badge tone="demo">AI-onderzocht</Badge>}
          </div>
        </div>
        <ChevronDown className={clsx("mt-1 h-4 w-4 shrink-0 text-slate-400 transition", open && "rotate-180")} />
      </button>
      {open && (
        <div className="space-y-3 border-t border-slate-200 p-3 text-sm">
          {issue.summary && <p className="text-slate-700">{issue.summary}</p>}
          {issue.symptoms && issue.symptoms.length > 0 && (
            <div>
              <div className="mb-1 text-xs font-semibold uppercase text-slate-500">Symptomen</div>
              <ul className="list-disc space-y-0.5 pl-5 text-slate-700">{issue.symptoms.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
          {issue.fix && (
            <div className="rounded-md bg-slate-50 p-2.5">
              <span className="font-medium">{FIX_LABEL[issue.fix.type] ?? issue.fix.type}: </span>
              <span className="text-slate-700">{issue.fix.description}</span>
            </div>
          )}
          {issue.questions && issue.questions.length > 0 && (
            <div>
              <div className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase text-brand-800"><HelpCircle className="h-3.5 w-3.5" />Vraag de verkoper</div>
              <ul className="list-disc space-y-0.5 pl-5 text-slate-800">{issue.questions.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
          {issue.verify && issue.verify.length > 0 && (
            <div>
              <div className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><Search className="h-3.5 w-3.5" />Zo controleer je het</div>
              <ul className="list-disc space-y-0.5 pl-5 text-slate-700">{issue.verify.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
          {issue.test_drive && issue.test_drive.length > 0 && (
            <div>
              <div className="mb-1 flex items-center gap-1 text-xs font-semibold uppercase text-slate-500"><Car className="h-3.5 w-3.5" />Tijdens de proefrit</div>
              <ul className="list-disc space-y-0.5 pl-5 text-slate-700">{issue.test_drive.map((s) => <li key={s}>{s}</li>)}</ul>
            </div>
          )}
          {issue.sources && issue.sources.length > 0 && (
            <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
              <span className="text-slate-500">Bronnen:</span>
              {issue.sources.map((s) => (
                <a key={s.url} href={s.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-0.5 text-brand-700 hover:underline">
                  {s.title} <ExternalLink className="h-3 w-3" />
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
