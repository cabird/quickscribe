import { useCallback, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Plus, Search } from "lucide-react";
import { ParticipantCard } from "@/components/people/ParticipantCard";
import { AddParticipantDialog } from "@/components/people/AddParticipantDialog";
import PersonDetailPage from "./PersonDetailPage";
import { useIsMobile } from "@/hooks/useIsMobile";
import { useParticipants } from "@/lib/queries";
import type { Participant } from "@/types/models";

type SortField = "name" | "last_seen" | "first_seen";
type SortOrder = "asc" | "desc";

export default function PeoplePage() {
  const isMobile = useIsMobile();
  const navigate = useNavigate();
  const { id: selectedId } = useParams<{ id: string }>();

  const [searchQuery, setSearchQuery] = useState("");
  const [sortField, setSortField] = useState<SortField>("name");
  const [sortOrder] = useState<SortOrder>("asc");
  const [showAddDialog, setShowAddDialog] = useState(false);

  const { data: participantsResponse, isLoading } = useParticipants();

  const participants: Participant[] = useMemo(
    () => participantsResponse?.data ?? [],
    [participantsResponse],
  );

  // Filter and sort
  const filteredParticipants = useMemo(() => {
    let result = participants;

    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (p) =>
          p.display_name.toLowerCase().includes(q) ||
          p.first_name?.toLowerCase().includes(q) ||
          p.last_name?.toLowerCase().includes(q) ||
          p.aliases?.some((a) => a.toLowerCase().includes(q)) ||
          p.email?.toLowerCase().includes(q) ||
          p.organization?.toLowerCase().includes(q)
      );
    }

    result = [...result].sort((a, b) => {
      const dir = sortOrder === "asc" ? 1 : -1;
      switch (sortField) {
        case "name":
          return dir * a.display_name.localeCompare(b.display_name);
        case "last_seen": {
          const aDate = a.last_seen ? new Date(a.last_seen).getTime() : 0;
          const bDate = b.last_seen ? new Date(b.last_seen).getTime() : 0;
          return dir * (bDate - aDate);
        }
        case "first_seen": {
          const aDate = a.first_seen ? new Date(a.first_seen).getTime() : 0;
          const bDate = b.first_seen ? new Date(b.first_seen).getTime() : 0;
          return dir * (aDate - bDate);
        }
        default:
          return 0;
      }
    });

    return result;
  }, [participants, searchQuery, sortField, sortOrder]);

  const handleSelectParticipant = useCallback(
    (participant: Participant) => {
      if (isMobile) {
        navigate(`/people/${participant.id}`);
      } else {
        navigate(`/people/${participant.id}`, { replace: true });
      }
    },
    [isMobile, navigate]
  );

  // On mobile, if we have a selectedId, show detail only
  if (isMobile && selectedId) {
    return <PersonDetailPage />;
  }

  const listPanel = (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Action bar */}
      <div className="space-y-2 border-b p-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search people..."
              className="pl-9 h-9"
            />
          </div>
          <Button
            variant="outline"
            size="sm"
            className="h-9 gap-1"
            onClick={() => setShowAddDialog(true)}
          >
            <Plus className="h-4 w-4" />
            <span className="hidden sm:inline">Add</span>
          </Button>
        </div>

        <div className="flex items-center gap-2">
          <Select
            value={sortField}
            onValueChange={(v) => { if (v !== null) setSortField(v as SortField); }}
          >
            <SelectTrigger className="h-8 w-[140px] text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="name">Sort by name</SelectItem>
              <SelectItem value="last_seen">Last seen</SelectItem>
              <SelectItem value="first_seen">First seen</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Participant list */}
      {isLoading ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      ) : filteredParticipants.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-muted-foreground">
          <p>{searchQuery ? "No matching people" : "No participants yet"}</p>
          {!searchQuery && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowAddDialog(true)}
            >
              Add a person
            </Button>
          )}
        </div>
      ) : (
        <ScrollArea className="min-h-0 flex-1">
          <div className="space-y-0.5 p-2">
            {filteredParticipants.map((participant) => (
              <ParticipantCard
                key={participant.id}
                participant={participant}
                isSelected={participant.id === selectedId}
                onClick={() => handleSelectParticipant(participant)}
              />
            ))}
          </div>
        </ScrollArea>
      )}
    </div>
  );

  // Mobile: list only
  if (isMobile) {
    return (
      <>
        {listPanel}
        <AddParticipantDialog
          open={showAddDialog}
          onOpenChange={setShowAddDialog}
        />
      </>
    );
  }

  // Desktop: split view
  return (
    <>
      <div className="flex h-full">
        <div className="w-[380px] shrink-0 border-r">{listPanel}</div>
        <div className="flex-1 overflow-hidden">
          {selectedId ? (
            <PersonDetailPage />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
              Select a person to view details
            </div>
          )}
        </div>
      </div>
      <AddParticipantDialog
        open={showAddDialog}
        onOpenChange={setShowAddDialog}
      />
    </>
  );
}
