import { useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Intervention } from "@/api/types";

function riskVariant(score: number) {
  if (score >= 0.7) return "danger" as const;
  if (score >= 0.4) return "warning" as const;
  return "success" as const;
}

function riskLabel(score: number): string {
  if (score >= 0.75) return "High";
  if (score >= 0.5) return "Medium";
  return "Low";
}

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  return new Date(iso).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

interface InterventionCardProps {
  intervention: Intervention;
  athleteName: string;
  onDecide: (intervention: Intervention, action: string) => void;
}

export function InterventionCard({
  intervention,
  athleteName,
  onDecide,
}: InterventionCardProps) {
  const [expanded, setExpanded] = useState(false);
  const isOpen = intervention.status === "open";

  return (
    <div className="rounded-lg border bg-card shadow-sm">
      {/* Header row — always visible */}
      <button
        type="button"
        className="flex w-full cursor-pointer items-center justify-between p-4 text-left"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3">
          <div className="space-y-1">
            <p className="text-sm font-medium">{athleteName}</p>
            <p className="text-xs capitalize text-muted-foreground">
              {intervention.action_type.replace(/_/g, " ")}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={riskVariant(intervention.risk_score)}>
            {riskLabel(intervention.risk_score)}{" "}
            {(intervention.risk_score * 100).toFixed(0)}%
          </Badge>
          <Badge variant="secondary">
            Conf {(intervention.confidence_score * 100).toFixed(0)}%
          </Badge>
          {!intervention.guardrail_pass && (
            <Badge variant="destructive">
              <ShieldAlert className="mr-1 h-3 w-3" />
              Blocked
            </Badge>
          )}
          {intervention.guardrail_pass && (
            <ShieldCheck className="h-4 w-4 text-emerald-500" />
          )}
          {expanded ? (
            <ChevronUp className="h-4 w-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </button>

      {/* Expandable detail section */}
      {expanded && (
        <div className="space-y-3 border-t px-4 pb-4 pt-3">
          {/* Why Factors */}
          {intervention.why_factors.length > 0 && (
            <div>
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                Why Factors
              </p>
              <div className="flex flex-wrap gap-1.5">
                {intervention.why_factors
                  .filter((f) => !f.startsWith("decision:"))
                  .map((factor, i) => (
                    <Badge key={i} variant="outline" className="text-xs">
                      {factor}
                    </Badge>
                  ))}
              </div>
            </div>
          )}

          {/* Guardrail Reason */}
          {intervention.guardrail_reason && (
            <div>
              <p className="mb-1 text-xs font-medium text-muted-foreground">
                Guardrail
              </p>
              <p className="text-sm">
                {intervention.guardrail_pass ? (
                  <span className="text-emerald-600">Pass</span>
                ) : (
                  <span className="text-red-600">Fail</span>
                )}
                {" — "}
                {intervention.guardrail_reason}
              </p>
            </div>
          )}

          {/* Cooldown */}
          {intervention.cooldown_until && (
            <div className="flex items-center gap-1 text-sm text-amber-600">
              <Clock className="h-3.5 w-3.5" />
              Snoozed until {formatDate(intervention.cooldown_until)}
            </div>
          )}

          {/* Created date */}
          <p className="text-xs text-muted-foreground">
            Created: {formatDate(intervention.created_at)}
          </p>

          {/* Action buttons — only for open interventions */}
          {isOpen && (
            <div className="flex items-center gap-2 pt-1">
              <Button
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onDecide(intervention, "accept_and_close");
                }}
              >
                <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                Accept
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => {
                  e.stopPropagation();
                  onDecide(intervention, "defer_24h");
                }}
              >
                <Clock className="mr-1.5 h-3.5 w-3.5" />
                Defer 24h
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={(e) => {
                  e.stopPropagation();
                  onDecide(intervention, "defer_72h");
                }}
              >
                <Clock className="mr-1.5 h-3.5 w-3.5" />
                Defer 72h
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={(e) => {
                  e.stopPropagation();
                  onDecide(intervention, "dismiss");
                }}
              >
                <XCircle className="mr-1.5 h-3.5 w-3.5" />
                Dismiss
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
