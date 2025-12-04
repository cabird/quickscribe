import { useState, useEffect } from 'react';
import {
  makeStyles,
  tokens,
  Card,
  CardHeader,
  Text,
  Spinner,
  Switch,
  Input,
  Button,
} from '@fluentui/react-components';
import {
  Person24Regular,
  Cloud24Regular,
  Save24Regular,
  Eye24Regular,
  EyeOff24Regular,
} from '@fluentui/react-icons';
import { userService } from '../../services/userService';
import type { User } from '../../types';
import { showToast } from '../../utils/toast';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    flexDirection: 'column',
    flex: 1,
    padding: '24px',
    overflowY: 'auto',
    backgroundColor: tokens.colorNeutralBackground2,
  },
  header: {
    marginBottom: '24px',
  },
  title: {
    fontSize: tokens.fontSizeBase600,
    fontWeight: tokens.fontWeightSemibold,
  },
  content: {
    display: 'flex',
    flexDirection: 'column',
    gap: '24px',
    maxWidth: '800px',
  },
  card: {
    padding: '20px',
  },
  cardTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontSize: tokens.fontSizeBase400,
    fontWeight: tokens.fontWeightSemibold,
  },
  fieldGroup: {
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    marginTop: '16px',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  fieldRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '16px',
  },
  fieldLabel: {
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
    fontWeight: tokens.fontWeightSemibold,
  },
  fieldValue: {
    fontSize: tokens.fontSizeBase300,
  },
  tokenInput: {
    flex: 1,
  },
  loadingContainer: {
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    flex: 1,
  },
  actions: {
    display: 'flex',
    gap: '8px',
    marginTop: '16px',
  },
});

export function SettingsView() {
  const styles = useStyles();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Plaud settings state
  const [enableSync, setEnableSync] = useState(false);
  const [bearerToken, setBearerToken] = useState('');
  const [showToken, setShowToken] = useState(false);
  const [hasChanges, setHasChanges] = useState(false);

  useEffect(() => {
    loadUser();
  }, []);

  const loadUser = async () => {
    try {
      setLoading(true);
      const userData = await userService.getCurrentUser();
      setUser(userData);
      setEnableSync(userData.plaudSettings?.enableSync ?? false);
      setBearerToken(userData.plaudSettings?.bearerToken ?? '');
    } catch (error) {
      showToast.error('Failed to load user settings');
      console.error('Error loading user:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEnableSyncChange = (checked: boolean) => {
    setEnableSync(checked);
    setHasChanges(true);
  };

  const handleBearerTokenChange = (value: string) => {
    setBearerToken(value);
    setHasChanges(true);
  };

  const handleSave = async () => {
    if (!user) return;

    try {
      setSaving(true);
      await userService.updatePlaudSettings(user.id, {
        enableSync,
        bearerToken,
      });
      showToast.success('Settings saved successfully');
      setHasChanges(false);
      // Reload to get updated data
      await loadUser();
    } catch (error) {
      showToast.error('Failed to save settings');
      console.error('Error saving settings:', error);
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never';
    try {
      return new Date(dateString).toLocaleString();
    } catch {
      return dateString;
    }
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loadingContainer}>
          <Spinner size="large" label="Loading settings..." />
        </div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className={styles.container}>
        <Text>Unable to load user settings</Text>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Text className={styles.title}>Settings</Text>
      </div>

      <div className={styles.content}>
        {/* Profile Info Card */}
        <Card className={styles.card}>
          <CardHeader
            header={
              <div className={styles.cardTitle}>
                <Person24Regular />
                <span>Profile</span>
              </div>
            }
          />
          <div className={styles.fieldGroup}>
            <div className={styles.field}>
              <Text className={styles.fieldLabel}>Name</Text>
              <Text className={styles.fieldValue}>{user.name || 'Not set'}</Text>
            </div>
            <div className={styles.field}>
              <Text className={styles.fieldLabel}>Email</Text>
              <Text className={styles.fieldValue}>{user.email || 'Not set'}</Text>
            </div>
            <div className={styles.fieldRow}>
              <div className={styles.field}>
                <Text className={styles.fieldLabel}>Role</Text>
                <Text className={styles.fieldValue}>{user.role || 'User'}</Text>
              </div>
              <div className={styles.field}>
                <Text className={styles.fieldLabel}>Member Since</Text>
                <Text className={styles.fieldValue}>{formatDate(user.created_at)}</Text>
              </div>
            </div>
            <div className={styles.field}>
              <Text className={styles.fieldLabel}>Last Login</Text>
              <Text className={styles.fieldValue}>{formatDate(user.last_login)}</Text>
            </div>
            <div className={styles.field}>
              <Text className={styles.fieldLabel}>User ID</Text>
              <Text className={styles.fieldValue}>{user.id}</Text>
            </div>
            <div className={styles.field}>
              <Text className={styles.fieldLabel}>Azure AD ID</Text>
              <Text className={styles.fieldValue}>{user.azure_oid || 'Not linked'}</Text>
            </div>
          </div>
        </Card>

        {/* Plaud Integration Card */}
        <Card className={styles.card}>
          <CardHeader
            header={
              <div className={styles.cardTitle}>
                <Cloud24Regular />
                <span>Plaud Integration</span>
              </div>
            }
          />
          <div className={styles.fieldGroup}>
            <Switch
              label="Enable Plaud Sync"
              checked={enableSync}
              onChange={(_, data) => handleEnableSyncChange(data.checked)}
            />

            <div className={styles.field}>
              <Text className={styles.fieldLabel}>Bearer Token</Text>
              <div className={styles.fieldRow}>
                <Input
                  className={styles.tokenInput}
                  type={showToken ? 'text' : 'password'}
                  value={bearerToken}
                  onChange={(_, data) => handleBearerTokenChange(data.value)}
                  placeholder="Enter your Plaud bearer token"
                />
                <Button
                  appearance="subtle"
                  icon={showToken ? <EyeOff24Regular /> : <Eye24Regular />}
                  onClick={() => setShowToken(!showToken)}
                />
              </div>
            </div>

            <div className={styles.actions}>
              <Button
                appearance="primary"
                icon={<Save24Regular />}
                onClick={handleSave}
                disabled={!hasChanges || saving}
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
