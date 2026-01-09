import {
  makeStyles,
  Input,
  Dropdown,
  Option,
  Button,
  tokens,
} from '@fluentui/react-components';
import {
  Search20Regular,
  ArrowSortDown20Regular,
  ArrowSortUp20Regular,
  Filter20Regular,
  ArrowClockwise20Regular,
  PersonAdd20Regular,
  Delete20Regular,
  Dismiss20Regular,
} from '@fluentui/react-icons';
import type { SortBy, SortOrder } from '../../hooks/usePeopleList';

const useStyles = makeStyles({
  container: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 16px',
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    flexWrap: 'wrap',
  },
  searchInput: {
    minWidth: '200px',
    flex: '1 1 200px',
    maxWidth: '300px',
  },
  dropdown: {
    minWidth: '140px',
  },
  sortButton: {
    minWidth: '32px',
  },
  spacer: {
    flex: 1,
  },
  selectionInfo: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  selectionCount: {
    fontSize: '14px',
    fontWeight: 500,
    color: tokens.colorNeutralForeground1,
  },
});

interface PeopleActionBarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  sortBy: SortBy;
  onSortByChange: (sortBy: SortBy) => void;
  sortOrder: SortOrder;
  onSortOrderChange: (order: SortOrder) => void;
  groupFilter: string;
  onGroupFilterChange: (group: string) => void;
  uniqueGroups: string[];
  onRefresh: () => void;
  onAddPerson: () => void;
  selectedCount: number;
  onClearSelections: () => void;
  onDeleteSelected: () => void;
}

const sortOptions: { value: SortBy; label: string }[] = [
  { value: 'name', label: 'Name' },
  { value: 'lastSeen', label: 'Last Seen' },
  { value: 'firstSeen', label: 'First Seen' },
];

export function PeopleActionBar({
  searchQuery,
  onSearchChange,
  sortBy,
  onSortByChange,
  sortOrder,
  onSortOrderChange,
  groupFilter,
  onGroupFilterChange,
  uniqueGroups,
  onRefresh,
  onAddPerson,
  selectedCount,
  onClearSelections,
  onDeleteSelected,
}: PeopleActionBarProps) {
  const styles = useStyles();

  const toggleSortOrder = () => {
    onSortOrderChange(sortOrder === 'asc' ? 'desc' : 'asc');
  };

  // Show bulk action UI when items are selected
  if (selectedCount > 0) {
    return (
      <div className={styles.container}>
        <div className={styles.selectionInfo}>
          <span className={styles.selectionCount}>{selectedCount} selected</span>
          <Button
            appearance="subtle"
            icon={<Dismiss20Regular />}
            onClick={onClearSelections}
          >
            Clear
          </Button>
        </div>

        <div className={styles.spacer} />

        <Button
          appearance="primary"
          icon={<Delete20Regular />}
          onClick={onDeleteSelected}
        >
          Delete Selected
        </Button>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <Input
        className={styles.searchInput}
        placeholder="Search people..."
        contentBefore={<Search20Regular />}
        value={searchQuery}
        onChange={(_, data) => onSearchChange(data.value)}
      />

      <Dropdown
        className={styles.dropdown}
        placeholder="Sort by"
        value={sortOptions.find(o => o.value === sortBy)?.label}
        selectedOptions={[sortBy]}
        onOptionSelect={(_, data) => {
          if (data.optionValue) {
            onSortByChange(data.optionValue as SortBy);
          }
        }}
      >
        {sortOptions.map(option => (
          <Option key={option.value} value={option.value}>
            {option.label}
          </Option>
        ))}
      </Dropdown>

      <Button
        className={styles.sortButton}
        appearance="subtle"
        icon={sortOrder === 'asc' ? <ArrowSortUp20Regular /> : <ArrowSortDown20Regular />}
        onClick={toggleSortOrder}
        title={sortOrder === 'asc' ? 'Ascending' : 'Descending'}
      />

      {uniqueGroups.length > 0 && (
        <Dropdown
          className={styles.dropdown}
          placeholder="All Groups"
          value={groupFilter || 'All Groups'}
          selectedOptions={groupFilter ? [groupFilter] : []}
          onOptionSelect={(_, data) => {
            onGroupFilterChange(data.optionValue === '__all__' ? '' : (data.optionValue as string));
          }}
        >
          <Option value="__all__" text="All Groups">
            <Filter20Regular style={{ marginRight: '8px' }} />
            All Groups
          </Option>
          {uniqueGroups.map(group => (
            <Option key={group} value={group}>
              {group}
            </Option>
          ))}
        </Dropdown>
      )}

      <div className={styles.spacer} />

      <Button
        appearance="primary"
        icon={<PersonAdd20Regular />}
        onClick={onAddPerson}
      >
        Add Person
      </Button>

      <Button
        appearance="subtle"
        icon={<ArrowClockwise20Regular />}
        onClick={onRefresh}
        title="Refresh"
      />
    </div>
  );
}
