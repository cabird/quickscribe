import {
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Text,
  Spinner,
} from '@fluentui/react-components';
import { Warning20Regular } from '@fluentui/react-icons';
import type { Participant } from '../../types';

interface DeleteConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  participant: Participant | null;
  isBulk: boolean;
  bulkCount: number;
  onConfirm: () => void;
  saving: boolean;
}

export function DeleteConfirmDialog({
  open,
  onOpenChange,
  participant,
  isBulk,
  bulkCount,
  onConfirm,
  saving,
}: DeleteConfirmDialogProps) {
  const handleClose = () => {
    if (!saving) {
      onOpenChange(false);
    }
  };

  const title = isBulk
    ? `Delete ${bulkCount} Participants?`
    : `Delete "${participant?.displayName}"?`;

  const warningMessage = isBulk
    ? `This will permanently delete ${bulkCount} participants. Speaker mappings in recordings will be unlinked (reverted to "Speaker X").`
    : `This will permanently delete this participant. Speaker mappings in recordings will be unlinked (reverted to "Speaker X").`;

  return (
    <Dialog open={open} onOpenChange={(_, data) => onOpenChange(data.open)}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>{title}</DialogTitle>
          <DialogContent>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
              <Warning20Regular style={{ color: '#DC2626', fontSize: '20px', flexShrink: 0, marginTop: '2px' }} />
              <Text>{warningMessage}</Text>
            </div>
            <Text
              style={{ display: 'block', marginTop: '12px', color: '#6B7280', fontSize: '13px' }}
            >
              This action cannot be undone.
            </Text>
          </DialogContent>
          <DialogActions>
            <Button
              appearance="secondary"
              onClick={handleClose}
              disabled={saving}
            >
              Cancel
            </Button>
            <Button
              appearance="primary"
              onClick={onConfirm}
              disabled={saving}
              style={{ backgroundColor: '#DC2626' }}
            >
              {saving ? <Spinner size="tiny" /> : 'Delete'}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
