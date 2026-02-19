import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";

interface InterventionFiltersProps {
  statusFilter: string;
  onStatusFilterChange: (value: string) => void;
  onSync: () => void;
  isSyncing: boolean;
  totalCount: number;
}

export function InterventionFilters({
  statusFilter,
  onStatusFilterChange,
  onSync,
  isSyncing,
  totalCount,
}: InterventionFiltersProps) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex items-center gap-3">
        <Select
          value={statusFilter}
          onChange={(e) => onStatusFilterChange(e.target.value)}
          className="w-36"
        >
          <option value="open">Open</option>
          <option value="closed">Closed</option>
          <option value="all">All</option>
        </Select>
        <span className="text-sm text-muted-foreground">
          {totalCount} intervention{totalCount !== 1 ? "s" : ""}
        </span>
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={onSync}
        disabled={isSyncing}
      >
        <RefreshCw
          className={`mr-2 h-4 w-4 ${isSyncing ? "animate-spin" : ""}`}
        />
        {isSyncing ? "Syncing..." : "Sync Queue"}
      </Button>
    </div>
  );
}
