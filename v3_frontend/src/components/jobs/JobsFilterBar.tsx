import { makeStyles, Button, Dropdown, Option, Switch, tokens } from '@fluentui/react-components';
import { ArrowClockwise24Regular, Filter24Regular } from '@fluentui/react-icons';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '16px 24px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    backgroundColor: tokens.colorNeutralBackground1,
    flexWrap: 'wrap',
  },
  filterGroup: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  spacer: {
    flex: 1,
  },
});

interface JobsFilterBarProps {
  minDuration: number | undefined;
  hasActivity: boolean;
  status: string;
  triggerSource: string;
  onMinDurationChange: (value: number | undefined) => void;
  onHasActivityChange: (value: boolean) => void;
  onStatusChange: (value: string) => void;
  onTriggerSourceChange: (value: string) => void;
  onRefresh: () => void;
}

export function JobsFilterBar({
  minDuration,
  hasActivity,
  status,
  triggerSource,
  onMinDurationChange,
  onHasActivityChange,
  onStatusChange,
  onTriggerSourceChange,
  onRefresh,
}: JobsFilterBarProps) {
  const styles = useStyles();

  return (
    <div className={styles.container}>
      <Filter24Regular style={{ color: tokens.colorNeutralForeground3 }} />

      <div className={styles.filterGroup}>
        <Switch
          label="Has Activity"
          checked={hasActivity}
          onChange={(_, data) => onHasActivityChange(data.checked)}
        />
      </div>

      <Dropdown
        placeholder="Duration"
        value={
          minDuration === undefined
            ? 'Any'
            : minDuration === 30
            ? '≥30s'
            : minDuration === 60
            ? '≥1m'
            : minDuration === 300
            ? '≥5m'
            : 'Custom'
        }
        onOptionSelect={(_, data) => {
          switch (data.optionValue) {
            case 'any':
              onMinDurationChange(undefined);
              break;
            case '30':
              onMinDurationChange(30);
              break;
            case '60':
              onMinDurationChange(60);
              break;
            case '300':
              onMinDurationChange(300);
              break;
          }
        }}
      >
        <Option value="any">Any</Option>
        <Option value="30">≥30s</Option>
        <Option value="60">≥1m</Option>
        <Option value="300">≥5m</Option>
      </Dropdown>

      <Dropdown
        placeholder="Status"
        value={
          status === ''
            ? 'All'
            : status === 'completed'
            ? 'Completed'
            : status === 'failed'
            ? 'Failed'
            : status === 'running'
            ? 'Running'
            : status === 'completed,failed'
            ? 'Completed + Failed'
            : 'Custom'
        }
        onOptionSelect={(_, data) => {
          onStatusChange(data.optionValue || '');
        }}
      >
        <Option value="">All</Option>
        <Option value="completed">Completed</Option>
        <Option value="failed">Failed</Option>
        <Option value="running">Running</Option>
        <Option value="completed,failed">Completed + Failed</Option>
      </Dropdown>

      <Dropdown
        placeholder="Trigger"
        value={
          triggerSource === ''
            ? 'Both'
            : triggerSource === 'scheduled'
            ? 'Scheduled'
            : 'Manual'
        }
        onOptionSelect={(_, data) => {
          onTriggerSourceChange(data.optionValue || '');
        }}
      >
        <Option value="">Both</Option>
        <Option value="scheduled">Scheduled</Option>
        <Option value="manual">Manual</Option>
      </Dropdown>

      <div className={styles.spacer} />

      <Button
        appearance="subtle"
        icon={<ArrowClockwise24Regular />}
        onClick={onRefresh}
      >
        Refresh
      </Button>
    </div>
  );
}
