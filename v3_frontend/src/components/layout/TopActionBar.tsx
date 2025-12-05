import { makeStyles, Input, Button, Dropdown, Option, tokens } from '@fluentui/react-components';
import { Search20Regular, ArrowExport20Regular, ArrowClockwise20Regular } from '@fluentui/react-icons';

const useStyles = makeStyles({
  actionBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    backgroundColor: tokens.colorNeutralBackground1,
  },
  searchInput: {
    minWidth: '300px',
  },
  dropdown: {
    minWidth: '150px',
  },
  spacer: {
    flex: 1,
  },
});

interface TopActionBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  searchType: 'basic' | 'fulltext';
  onSearchTypeChange: (type: 'basic' | 'fulltext') => void;
  dateRange: 'all' | 'week' | 'month' | 'quarter';
  onDateRangeChange: (range: 'all' | 'week' | 'month' | 'quarter') => void;
  onExport: () => void;
  onRefresh: () => void;
}

export function TopActionBar({
  searchQuery,
  onSearchChange,
  searchType,
  onSearchTypeChange,
  dateRange,
  onDateRangeChange,
  onExport,
  onRefresh,
}: TopActionBarProps) {
  const styles = useStyles();

  return (
    <div className={styles.actionBar}>
      <Input
        className={styles.searchInput}
        contentBefore={<Search20Regular />}
        placeholder="Search recordings..."
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
      />

      <Dropdown
        className={styles.dropdown}
        placeholder="Search type"
        value={searchType === 'basic' ? 'Basic' : 'Full-text'}
        selectedOptions={[searchType]}
        onOptionSelect={(_, data) => onSearchTypeChange(data.optionValue as 'basic' | 'fulltext')}
      >
        <Option value="basic">Basic</Option>
        <Option value="fulltext">Full-text</Option>
      </Dropdown>

      <Dropdown
        className={styles.dropdown}
        placeholder="Date range"
        value={dateRange.charAt(0).toUpperCase() + dateRange.slice(1)}
        selectedOptions={[dateRange]}
        onOptionSelect={(_, data) => onDateRangeChange(data.optionValue as 'all' | 'week' | 'month' | 'quarter')}
      >
        <Option value="all">All</Option>
        <Option value="week">Past Week</Option>
        <Option value="month">Past Month</Option>
        <Option value="quarter">Past Quarter</Option>
      </Dropdown>

      <div className={styles.spacer} />

      <Button
        appearance="subtle"
        icon={<ArrowExport20Regular />}
        onClick={onExport}
      >
        Export
      </Button>

      <Button
        appearance="subtle"
        icon={<ArrowClockwise20Regular />}
        onClick={onRefresh}
      >
        Refresh
      </Button>
    </div>
  );
}
