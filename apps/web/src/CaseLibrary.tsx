import { useEffect, useState } from "react";
import type { Case } from "../../../packages/scene/types";

const groups = [
  { id: "illustrations", title: "Illustrated object scenes" },
  { id: "prompt", title: "Procedural layouts" },
  { id: "reference", title: "Original photos & diagrams" },
  { id: "generated", title: "Generated scene images" },
  { id: "synthetic", title: "Synthetic photo comparisons" },
  { id: "real", title: "Real-photo reconstructions" },
] as const;

function groupFor(item: Case): typeof groups[number]["id"] {
  if (item.id.endsWith("-illustrated")) return "illustrations";
  if (/^T\d+-/.test(item.id)) return "synthetic";
  if (/^R\d+-/.test(item.id)) return "real";
  if (item.input_type === "prompt") return "prompt";
  return item.input_type === "generated" ? "generated" : "reference";
}

type Props = {
  cases: Case[];
  caseId: string;
  busy: boolean;
  onSelect: (id: string) => void;
  statusForCase: (item: Case) => string;
};

function CaseGroup({ title, items, caseId, busy, onSelect, statusForCase }: Omit<Props, "cases"> & { title: string; items: Case[] }) {
  const active = items.some(item => item.id === caseId);
  const [open, setOpen] = useState(active);
  useEffect(() => { if (active) setOpen(true); }, [active, caseId]);
  return <details className="case-group" open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary><span className="case-group-title">{title}</span><span className="count" aria-label={`${items.length} cases`}>{items.length}</span></summary>
    {items.map(item => <button key={item.id} className={`case-item ${caseId === item.id ? "active" : ""}`} onClick={() => onSelect(item.id)} disabled={busy} aria-current={caseId === item.id ? "page" : undefined}>
      <span className="case-id">{item.id}</span><span className="case-name">{item.title}<small>{statusForCase(item)}</small></span><span className={`status-dot ${item.status}`} aria-hidden="true" />
    </button>)}
  </details>;
}

export default function CaseLibrary({ cases, ...props }: Props) {
  return <>{groups.map(group => {
    const items = cases.filter(item => groupFor(item) === group.id);
    return items.length ? <CaseGroup key={group.id} title={group.title} items={items} {...props} /> : null;
  })}</>;
}
