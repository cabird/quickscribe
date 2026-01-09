import { useState, useCallback } from 'react';
import {
  Dialog,
  DialogSurface,
  DialogBody,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Input,
  Textarea,
  Text,
  Spinner,
  makeStyles,
  tokens,
} from '@fluentui/react-components';
import {
  Person20Regular,
  Mail20Regular,
  Briefcase20Regular,
  Building20Regular,
  PersonLink20Regular,
} from '@fluentui/react-icons';
import type { CreateParticipantRequest } from '../../types';

const useStyles = makeStyles({
  form: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
  },
  infoGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(2, 1fr)',
    gap: '16px',
  },
  infoItem: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  infoItemFullWidth: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
    gridColumn: 'span 2',
  },
  infoLabel: {
    fontSize: '12px',
    color: '#9CA3AF',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  },
  requiredLabel: {
    fontSize: '12px',
    color: '#9CA3AF',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    '::after': {
      content: '"*"',
      color: tokens.colorPaletteRedForeground1,
      marginLeft: '2px',
    },
  },
  input: {
    width: '100%',
  },
  aliasHint: {
    fontSize: '12px',
    color: '#6B7280',
    marginTop: '4px',
  },
  errorText: {
    color: tokens.colorPaletteRedForeground1,
    fontSize: '12px',
    marginTop: '4px',
  },
  savingOverlay: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
});

interface AddParticipantDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (data: CreateParticipantRequest) => Promise<void>;
  saving?: boolean;
}

export function AddParticipantDialog({
  open,
  onOpenChange,
  onSave,
  saving = false,
}: AddParticipantDialogProps) {
  const styles = useStyles();
  const [form, setForm] = useState<CreateParticipantRequest>({
    displayName: '',
  });
  const [error, setError] = useState<string | null>(null);

  const resetForm = useCallback(() => {
    setForm({ displayName: '' });
    setError(null);
  }, []);

  const handleClose = useCallback(() => {
    if (!saving) {
      resetForm();
      onOpenChange(false);
    }
  }, [saving, resetForm, onOpenChange]);

  const handleSave = useCallback(async () => {
    // Validate displayName
    if (!form.displayName?.trim()) {
      setError('Display name is required');
      return;
    }

    setError(null);

    // Clean up the data before sending
    const data: CreateParticipantRequest = {
      displayName: form.displayName.trim(),
    };

    if (form.firstName?.trim()) {
      data.firstName = form.firstName.trim();
    }
    if (form.lastName?.trim()) {
      data.lastName = form.lastName.trim();
    }
    if (form.email?.trim()) {
      data.email = form.email.trim();
    }
    if (form.role?.trim()) {
      data.role = form.role.trim();
    }
    if (form.organization?.trim()) {
      data.organization = form.organization.trim();
    }
    if (form.relationshipToUser?.trim()) {
      data.relationshipToUser = form.relationshipToUser.trim();
    }
    if (form.notes?.trim()) {
      data.notes = form.notes.trim();
    }
    if (form.aliases && form.aliases.length > 0) {
      data.aliases = form.aliases;
    }

    try {
      await onSave(data);
      resetForm();
      onOpenChange(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create participant');
    }
  }, [form, onSave, resetForm, onOpenChange]);

  const handleAliasesChange = useCallback((value: string) => {
    // Split by commas and trim each alias
    const aliases = value
      .split(',')
      .map(a => a.trim())
      .filter(a => a.length > 0);
    setForm(prev => ({ ...prev, aliases }));
  }, []);

  return (
    <Dialog open={open} onOpenChange={(_, data) => !saving && onOpenChange(data.open)}>
      <DialogSurface>
        <DialogBody>
          <DialogTitle>Add Person</DialogTitle>
          <DialogContent>
            <div className={styles.form}>
              {/* Display Name - Required */}
              <div className={styles.infoItem}>
                <Text className={styles.requiredLabel}>
                  <Person20Regular />
                  Display Name
                </Text>
                <Input
                  className={styles.input}
                  value={form.displayName || ''}
                  onChange={(_, data) => {
                    setForm(prev => ({ ...prev, displayName: data.value }));
                    if (error) setError(null);
                  }}
                  placeholder="How this person should be displayed"
                  disabled={saving}
                  required
                />
                {error && <Text className={styles.errorText}>{error}</Text>}
              </div>

              <div className={styles.infoGrid}>
                <div className={styles.infoItem}>
                  <Text className={styles.infoLabel}>
                    <Person20Regular />
                    First Name
                  </Text>
                  <Input
                    className={styles.input}
                    value={form.firstName || ''}
                    onChange={(_, data) => setForm(prev => ({ ...prev, firstName: data.value }))}
                    placeholder="First name"
                    disabled={saving}
                  />
                </div>
                <div className={styles.infoItem}>
                  <Text className={styles.infoLabel}>
                    <Person20Regular />
                    Last Name
                  </Text>
                  <Input
                    className={styles.input}
                    value={form.lastName || ''}
                    onChange={(_, data) => setForm(prev => ({ ...prev, lastName: data.value }))}
                    placeholder="Last name"
                    disabled={saving}
                  />
                </div>
                <div className={styles.infoItem}>
                  <Text className={styles.infoLabel}>
                    <Mail20Regular />
                    Email
                  </Text>
                  <Input
                    className={styles.input}
                    value={form.email || ''}
                    onChange={(_, data) => setForm(prev => ({ ...prev, email: data.value }))}
                    placeholder="email@example.com"
                    type="email"
                    disabled={saving}
                  />
                </div>
                <div className={styles.infoItem}>
                  <Text className={styles.infoLabel}>
                    <Briefcase20Regular />
                    Role
                  </Text>
                  <Input
                    className={styles.input}
                    value={form.role || ''}
                    onChange={(_, data) => setForm(prev => ({ ...prev, role: data.value }))}
                    placeholder="e.g., Project Manager"
                    disabled={saving}
                  />
                </div>
                <div className={styles.infoItem}>
                  <Text className={styles.infoLabel}>
                    <Building20Regular />
                    Group
                  </Text>
                  <Input
                    className={styles.input}
                    value={form.organization || ''}
                    onChange={(_, data) => setForm(prev => ({ ...prev, organization: data.value }))}
                    placeholder="e.g., Acme Corp"
                    disabled={saving}
                  />
                </div>
                <div className={styles.infoItem}>
                  <Text className={styles.infoLabel}>
                    <PersonLink20Regular />
                    Relationship
                  </Text>
                  <Input
                    className={styles.input}
                    value={form.relationshipToUser || ''}
                    onChange={(_, data) => setForm(prev => ({ ...prev, relationshipToUser: data.value }))}
                    placeholder="e.g., Colleague, Client"
                    disabled={saving}
                  />
                </div>

                {/* Aliases - Full Width */}
                <div className={styles.infoItemFullWidth}>
                  <Text className={styles.infoLabel}>Aliases</Text>
                  <Input
                    className={styles.input}
                    value={(form.aliases || []).join(', ')}
                    onChange={(_, data) => handleAliasesChange(data.value)}
                    placeholder="Add aliases separated by commas"
                    disabled={saving}
                  />
                  <Text className={styles.aliasHint}>
                    Separate multiple aliases with commas (e.g., "Johnny, J. Smith")
                  </Text>
                </div>

                {/* Notes - Full Width */}
                <div className={styles.infoItemFullWidth}>
                  <Text className={styles.infoLabel}>Notes</Text>
                  <Textarea
                    value={form.notes || ''}
                    onChange={(_, data) => setForm(prev => ({ ...prev, notes: data.value }))}
                    placeholder="Add notes about this person..."
                    resize="vertical"
                    style={{ width: '100%', minHeight: '80px' }}
                    disabled={saving}
                  />
                </div>
              </div>
            </div>
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
              onClick={handleSave}
              disabled={!form.displayName?.trim() || saving}
            >
              {saving ? (
                <span className={styles.savingOverlay}>
                  <Spinner size="tiny" />
                  Creating...
                </span>
              ) : (
                'Add Person'
              )}
            </Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
