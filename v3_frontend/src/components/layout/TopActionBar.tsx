import { makeStyles, Input, Button, Dropdown, Option, tokens, Text } from '@fluentui/react-components';
import { Search20Regular, ArrowExport20Regular, ArrowClockwise20Regular, Checkmark20Filled, Dismiss20Regular, Chat20Regular, NumberSymbol20Regular } from '@fluentui/react-icons';
import { formatTokenCount } from '../../utils/formatters';

const useStyles = makeStyles({
  actionBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.08)',
    zIndex: 10,
    position: 'relative',
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
  selectionInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '4px 12px',
    borderRadius: '6px',
    backgroundColor: tokens.colorNeutralBackground3,
  },
  selectionCount: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    color: tokens.colorBrandForeground1,
    fontWeight: 600,
  },
  tokenCount: {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    color: tokens.colorNeutralForeground2,
  },
  tokenCountWarning: {
    color: '#D97706', // Amber warning color
  },
  separator: {
    color: tokens.colorNeutralStroke1,
    margin: '0 4px',
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
  // Selection props
  selectedCount: number;
  selectedTokenCount: number;
  onClearSelection: () => void;
  onChatWithSelected: () => void;
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
  selectedCount,
  selectedTokenCount,
  onClearSelection,
  onChatWithSelected,
}: TopActionBarProps) {
  const styles = useStyles();
  const isTokenCountHigh = selectedTokenCount > 100000;

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

      {/* Selection info - shown when recordings are selected */}
      {selectedCount > 0 && (
        <>
          <div className={styles.selectionInfo}>
            <span className={styles.selectionCount}>
              <Checkmark20Filled />
              <Text weight="semibold">{selectedCount}</Text>
            </span>
            <span className={styles.separator}>•</span>
            <span className={`${styles.tokenCount} ${isTokenCountHigh ? styles.tokenCountWarning : ''}`}>
              <NumberSymbol20Regular />
              <Text>{formatTokenCount(selectedTokenCount)}</Text>
            </span>
          </div>
          <Button
            appearance="subtle"
            icon={<Dismiss20Regular />}
            onClick={onClearSelection}
            title="Clear selection"
          />
          <Button
            appearance="primary"
            icon={<Chat20Regular />}
            onClick={onChatWithSelected}
          >
            Chat
          </Button>
        </>
      )}

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
