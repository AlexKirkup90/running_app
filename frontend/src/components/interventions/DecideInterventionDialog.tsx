import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Intervention } from "@/api/types";

const DECISION_LABELS: Record<string, string> = {
  accept_and_close: "Accept & Close",
  defer_24h: "Defer 24 hours",
  defer_72h: "Defer 72 hours",
  dismiss: "Dismiss",
};

interface DecideInterventionDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  intervention: Intervention | null;
  decision: string;
  onConfirm: (note: string) => void;
  isPending: boolean;
}

export function DecideInterventionDialog({
  open,
  onOpenChange,
  intervention,
  decision,
  onConfirm,
  isPending,
}: DecideInterventionDialogProps) {
  const [note, setNote] = useState("");

  const handleConfirm = () => {
    onConfirm(note);
    setNote("");
  };

  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) setNote("");
    onOpenChange(nextOpen);
  };

  if (!intervention) return null;

  const isDestructive = decision === "dismiss";
  const label = DECISION_LABELS[decision] ?? decision;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{label} Intervention #{intervention.id}</DialogTitle>
          <DialogDescription>
            {intervention.action_type.replace(/_/g, " ")} — Risk:{" "}
            {(intervention.risk_score * 100).toFixed(0)}%
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-2">
            <Label htmlFor="decision-note">Note (optional)</Label>
            <Textarea
              id="decision-note"
              placeholder="Add context for this decision..."
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => handleOpenChange(false)}
            disabled={isPending}
          >
            Cancel
          </Button>
          <Button
            variant={isDestructive ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={isPending}
          >
            {isPending ? "Applying..." : `Confirm ${label}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
