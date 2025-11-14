import React, { useState } from 'react';
import {
  FluentProvider,
  webLightTheme,
  makeStyles,
  tokens,
  Button,
  Tooltip,
  Input,
  Dropdown,
  Option,
  Text,
  Card,
  CardHeader,
  Divider,
  Badge,
  Textarea,
  shorthands,
} from '@fluentui/react-components';
import {
  DocumentTextRegular,
  DocumentTextFilled,
  ChartMultipleRegular,
  ChartMultipleFilled,
  SearchRegular,
  SearchFilled,
  ArrowDownloadRegular,
  ArrowSyncRegular,
  FilterRegular,
  CalendarRegular,
  ClockRegular,
  PeopleRegular,
} from '@fluentui/react-icons';

// Styles
const useStyles = makeStyles({
  container: {
    display: 'flex',
    height: '100vh',
    backgroundColor: tokens.colorNeutralBackground2,
  },
  
  // Navigation Rail
  navRail: {
    width: '68px',
    backgroundColor: '#2c3e50',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    paddingTop: '12px',
    gap: '8px',
    boxShadow: tokens.shadow16,
  },
  navButton: {
    width: '48px',
    height: '48px',
    minWidth: '48px',
    padding: '0',
    fontSize: '20px',
    color: 'white',
    '&:hover': {
      backgroundColor: 'rgba(255,255,255,0.1)',
    },
  },
  navButtonActive: {
    backgroundColor: 'rgba(255,255,255,0.2)',
    position: 'relative',
    '&:hover': {
      backgroundColor: 'rgba(255,255,255,0.2)',
    },
    '&::before': {
      content: '""',
      position: 'absolute',
      left: '0',
      top: '50%',
      transform: 'translateY(-50%)',
      width: '3px',
      height: '24px',
      backgroundColor: '#4CAF50',
      borderRadius: '0 2px 2px 0',
    },
  },
  
  // Main Content
  mainContent: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  
  // Top Bar
  topBar: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '12px 20px',
    backgroundColor: tokens.colorNeutralBackground1,
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    boxShadow: tokens.shadow4,
  },
  searchContainer: {
    display: 'flex',
    gap: '8px',
    flex: 1,
    maxWidth: '500px',
  },
  
  // Content Views
  viewContainer: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
  
  // List Panel
  listPanel: {
    width: '35%',
    backgroundColor: tokens.colorNeutralBackground1,
    borderRight: `1px solid ${tokens.colorNeutralStroke1}`,
    overflowY: 'auto',
  },
  recordingItem: {
    padding: '16px 20px',
    borderBottom: `1px solid ${tokens.colorNeutralStroke1}`,
    cursor: 'pointer',
    transition: 'all 0.2s',
    '&:hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  recordingItemSelected: {
    backgroundColor: '#e8f5e9',
    borderLeft: `3px solid #4CAF50`,
    paddingLeft: '17px',
  },
  recordingTitle: {
    fontSize: '15px',
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground1,
    marginBottom: '4px',
  },
  recordingMeta: {
    display: 'flex',
    gap: '12px',
    fontSize: '13px',
    color: tokens.colorNeutralForeground3,
    marginBottom: '4px',
    alignItems: 'center',
  },
  recordingDescription: {
    fontSize: '13px',
    color: tokens.colorNeutralForeground2,
    ...shorthands.overflow('hidden'),
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    marginBottom: '4px',
  },
  recordingSpeakers: {
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
  },
  
  // Transcript Panel
  transcriptPanel: {
    flex: 1,
    padding: '30px 40px',
    backgroundColor: tokens.colorNeutralBackground1,
    overflowY: 'auto',
  },
  transcriptHeader: {
    marginBottom: '30px',
    paddingBottom: '20px',
    borderBottom: `2px solid ${tokens.colorNeutralStroke1}`,
  },
  transcriptTitle: {
    fontSize: '24px',
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground1,
    marginBottom: '8px',
  },
  transcriptInfo: {
    fontSize: '14px',
    color: tokens.colorNeutralForeground3,
  },
  transcriptEntry: {
    display: 'flex',
    gap: '20px',
    marginBottom: '24px',
  },
  transcriptTime: {
    minWidth: '50px',
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
    paddingTop: '2px',
  },
  transcriptContent: {
    flex: 1,
  },
  transcriptSpeaker: {
    fontWeight: tokens.fontWeightSemibold,
    color: '#2c3e50',
    marginBottom: '4px',
    fontSize: '14px',
  },
  transcriptText: {
    fontSize: '15px',
    lineHeight: '1.6',
    color: tokens.colorNeutralForeground1,
  },
  
  // Logs View
  logsContainer: {
    flex: 1,
    backgroundColor: '#1e1e1e',
    padding: '20px',
    fontFamily: 'Consolas, Monaco, monospace',
    fontSize: '13px',
    overflowY: 'auto',
    color: '#d4d4d4',
  },
  logEntry: {
    display: 'flex',
    gap: '12px',
    padding: '8px 12px',
    marginBottom: '4px',
    borderRadius: '4px',
    alignItems: 'center',
  },
  logError: {
    backgroundColor: 'rgba(244, 67, 54, 0.1)',
    borderLeft: '3px solid #f44336',
  },
  logWarning: {
    backgroundColor: 'rgba(255, 152, 0, 0.1)',
    borderLeft: '3px solid #ff9800',
  },
  logInfo: {
    backgroundColor: 'rgba(76, 175, 80, 0.1)',
    borderLeft: '3px solid #4CAF50',
  },
  logTime: {
    color: '#888',
    fontSize: '12px',
  },
  logLevel: {
    padding: '2px 6px',
    borderRadius: '3px',
    fontSize: '11px',
    fontWeight: 'bold',
    textTransform: 'uppercase',
  },
  logMessage: {
    flex: 1,
  },
  
  // Search View
  searchView: {
    flex: 1,
    padding: '40px',
    backgroundColor: tokens.colorNeutralBackground1,
  },
  searchHeader: {
    fontSize: '20px',
    fontWeight: tokens.fontWeightSemibold,
    marginBottom: '32px',
    textAlign: 'center',
    color: tokens.colorNeutralForeground1,
  },
  searchBox: {
    maxWidth: '700px',
    margin: '0 auto 32px',
  },
  searchButton: {
    marginTop: '16px',
  },
  searchResults: {
    maxWidth: '700px',
    margin: '0 auto',
  },
  searchResult: {
    marginBottom: '16px',
    padding: '16px',
    backgroundColor: tokens.colorNeutralBackground2,
    borderRadius: '8px',
    border: `1px solid ${tokens.colorNeutralStroke1}`,
  },
  searchResultTitle: {
    fontWeight: tokens.fontWeightSemibold,
    fontSize: '16px',
    marginBottom: '8px',
    color: tokens.colorNeutralForeground1,
  },
  searchResultMeta: {
    fontSize: '12px',
    color: tokens.colorNeutralForeground3,
    marginBottom: '12px',
  },
  searchResultSnippet: {
    fontSize: '14px',
    lineHeight: '1.6',
    color: tokens.colorNeutralForeground2,
    padding: '12px',
    backgroundColor: tokens.colorNeutralBackground1,
    borderLeft: `3px solid #4CAF50`,
    borderRadius: '4px',
  },
  emptyState: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    height: '100%',
    fontSize: '18px',
    color: tokens.colorNeutralForeground3,
  },
});

// Sample data
const sampleRecordings = [
  {
    id: 1,
    title: 'Q4 Planning Meeting',
    date: '2024-01-15',
    time: '2:00 PM',
    duration: '45 min',
    speakers: ['John Smith', 'Sarah Johnson', 'Mike Chen'],
    description: 'Quarterly planning discussion for Q4 2024 objectives and KPIs',
    transcript: [
      { time: '00:00', speaker: 'John Smith', text: 'Good afternoon everyone. Let\'s kick off our Q4 planning session. I\'d like to start by reviewing our Q3 performance and then dive into our objectives for the final quarter.' },
      { time: '00:45', speaker: 'Sarah Johnson', text: 'Thanks John. Looking at our Q3 metrics, we exceeded our targets in customer acquisition by 15%, but we fell short on retention by about 5%. I think we need to address this in Q4.' },
      { time: '01:30', speaker: 'Mike Chen', text: 'I agree with Sarah. The data shows that most churn happens in the first 30 days. We should focus on improving our onboarding process. I\'ve prepared a proposal that could reduce early churn by up to 20%.' },
      { time: '02:15', speaker: 'John Smith', text: 'That\'s excellent, Mike. Can you walk us through the key points of your proposal?' },
      { time: '02:45', speaker: 'Mike Chen', text: 'Absolutely. The main pillars are: personalized onboarding flows based on customer segment, proactive check-ins at days 7, 14, and 21, and a dedicated success manager for enterprise accounts.' },
    ]
  },
  {
    id: 2,
    title: 'Product Demo - Client ABC',
    date: '2024-01-14',
    time: '10:00 AM',
    duration: '30 min',
    speakers: ['Emma Wilson', 'David Brown'],
    description: 'Product demonstration for ABC Corporation stakeholders',
    transcript: [
      { time: '00:00', speaker: 'Emma Wilson', text: 'Welcome everyone from ABC Corporation. Today I\'ll be showing you our latest platform features and how they can streamline your workflow.' },
      { time: '00:30', speaker: 'David Brown', text: 'Thanks for having us, Emma. We\'re particularly interested in the integration capabilities with our existing CRM system.' },
      { time: '01:00', speaker: 'Emma Wilson', text: 'Perfect! Let me show you our native Salesforce integration first. As you can see here, all data syncs in real-time...' },
    ]
  },
  {
    id: 3,
    title: 'Team Standup',
    date: '2024-01-14',
    time: '9:00 AM',
    duration: '15 min',
    speakers: ['Alex Martinez', 'Lisa Park', 'Tom Anderson'],
    description: 'Daily standup meeting for the engineering team',
    transcript: [
      { time: '00:00', speaker: 'Alex Martinez', text: 'Morning team! Let\'s do a quick round of updates. I\'ll start - yesterday I finished the API refactoring and today I\'m starting on the new authentication module.' },
      { time: '00:45', speaker: 'Lisa Park', text: 'I\'m still working on the mobile app bug fixes. Found the issue with the crash on Android 12, should have a fix by noon.' },
      { time: '01:15', speaker: 'Tom Anderson', text: 'I\'m blocked on the payment integration. Need access to the Stripe test environment. Can someone help with that?' },
    ]
  },
];

const sampleLogs = [
  { level: 'error', time: '2024-01-15 14:23:45', message: 'Failed to process audio file: Invalid format' },
  { level: 'warning', time: '2024-01-15 14:22:31', message: 'Transcript processing took longer than expected (>30s)' },
  { level: 'info', time: '2024-01-15 14:20:15', message: 'Successfully generated transcript for meeting ID: 1234' },
  { level: 'info', time: '2024-01-15 14:18:02', message: 'New recording uploaded: Q4 Planning Meeting' },
  { level: 'debug', time: '2024-01-15 14:17:45', message: 'CosmosDB connection established successfully' },
];

export default function App() {
  const styles = useStyles();
  const [activeView, setActiveView] = useState('transcripts');
  const [selectedRecording, setSelectedRecording] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchType, setSearchType] = useState('basic');
  const [ragQuery, setRagQuery] = useState('');
  const [ragResults, setRagResults] = useState([]);

  // Navigation items configuration
  const navItems = [
    { id: 'transcripts', icon: DocumentTextRegular, iconFilled: DocumentTextFilled, label: 'Transcripts' },
    { id: 'logs', icon: ChartMultipleRegular, iconFilled: ChartMultipleFilled, label: 'Service Logs' },
    { id: 'search', icon: SearchRegular, iconFilled: SearchFilled, label: 'RAG Search' },
  ];

  // Handle RAG search
  const handleRAGSearch = () => {
    if (!ragQuery) return;
    
    // Mock search results
    setRagResults([
      {
        id: 1,
        title: 'Q4 Planning Meeting - Customer Retention Discussion',
        snippet: '...we fell short on retention by about 5%. I think we need to address this in Q4. The data shows that most churn happens in the first 30 days...',
        relevance: 95,
        speakers: 'Sarah Johnson, Mike Chen',
        date: 'January 15, 2024',
      },
      {
        id: 2,
        title: 'Customer Feedback Session - Dashboard Requirements',
        snippet: '...The current dashboard doesn\'t give us the granularity we need for our monthly reports. We need better filtering options...',
        relevance: 82,
        speakers: 'Rachel Green, Customer Panel',
        date: 'January 13, 2024',
      },
    ]);
  };

  // Filter recordings based on search
  const filteredRecordings = sampleRecordings.filter(recording => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    
    if (searchType === 'basic') {
      return recording.title.toLowerCase().includes(query) ||
             recording.description.toLowerCase().includes(query) ||
             recording.speakers.some(s => s.toLowerCase().includes(query));
    } else {
      return recording.transcript.some(entry => 
        entry.text.toLowerCase().includes(query)
      );
    }
  });

  // Render navigation rail
  const renderNavRail = () => (
    <div className={styles.navRail}>
      {navItems.map((item) => {
        const Icon = activeView === item.id ? item.iconFilled : item.icon;
        const isActive = activeView === item.id;
        
        return (
          <Tooltip
            key={item.id}
            content={item.label}
            relationship="label"
            positioning="after"
          >
            <Button
              appearance="subtle"
              className={`${styles.navButton} ${isActive ? styles.navButtonActive : ''}`}
              icon={<Icon />}
              onClick={() => setActiveView(item.id)}
            />
          </Tooltip>
        );
      })}
    </div>
  );

  // Render transcripts view
  const renderTranscriptsView = () => (
    <>
      <div className={styles.topBar}>
        <div className={styles.searchContainer}>
          <Input
            placeholder="Search recordings..."
            value={searchQuery}
            onChange={(e, data) => setSearchQuery(data.value)}
            contentBefore={<SearchRegular />}
          />
          <Dropdown
            value={searchType}
            onOptionSelect={(e, data) => setSearchType(data.optionValue)}
          >
            <Option value="basic">Basic Search</Option>
            <Option value="fulltext">Full Text Search</Option>
          </Dropdown>
        </div>
        <Dropdown defaultValue="all">
          <Option value="all">All Time</Option>
          <Option value="week">This Week</Option>
          <Option value="month">This Month</Option>
        </Dropdown>
        <Button icon={<ArrowDownloadRegular />}>Export</Button>
        <Button icon={<ArrowSyncRegular />}>Refresh</Button>
      </div>
      
      <div className={styles.viewContainer}>
        <div className={styles.listPanel}>
          {filteredRecordings.map(recording => (
            <div
              key={recording.id}
              className={`${styles.recordingItem} ${
                selectedRecording?.id === recording.id ? styles.recordingItemSelected : ''
              }`}
              onClick={() => setSelectedRecording(recording)}
            >
              <div className={styles.recordingTitle}>{recording.title}</div>
              <div className={styles.recordingMeta}>
                <span><CalendarRegular fontSize={12} /> {recording.date}</span>
                <span><ClockRegular fontSize={12} /> {recording.time}</span>
                <span>{recording.duration}</span>
              </div>
              <div className={styles.recordingDescription}>{recording.description}</div>
              <div className={styles.recordingSpeakers}>
                <PeopleRegular fontSize={12} />
                <span>{recording.speakers.join(', ')}</span>
              </div>
            </div>
          ))}
        </div>
        
        <div className={styles.transcriptPanel}>
          {selectedRecording ? (
            <>
              <div className={styles.transcriptHeader}>
                <div className={styles.transcriptTitle}>{selectedRecording.title}</div>
                <div className={styles.transcriptInfo}>
                  {selectedRecording.date}  {selectedRecording.time}  {selectedRecording.duration}  
                  Speakers: {selectedRecording.speakers.join(', ')}
                </div>
              </div>
              
              {selectedRecording.transcript.map((entry, index) => (
                <div key={index} className={styles.transcriptEntry}>
                  <div className={styles.transcriptTime}>{entry.time}</div>
                  <div className={styles.transcriptContent}>
                    <div className={styles.transcriptSpeaker}>{entry.speaker}</div>
                    <div className={styles.transcriptText}>{entry.text}</div>
                  </div>
                </div>
              ))}
            </>
          ) : (
            <div className={styles.emptyState}>Select a recording to view transcript</div>
          )}
        </div>
      </div>
    </>
  );

  // Render logs view
  const renderLogsView = () => (
    <>
      <div className={styles.topBar}>
        <div className={styles.searchContainer}>
          <Input
            placeholder="Filter logs..."
            contentBefore={<FilterRegular />}
          />
          <Dropdown defaultValue="all">
            <Option value="all">All Levels</Option>
            <Option value="error">Errors</Option>
            <Option value="warning">Warnings</Option>
            <Option value="info">Info</Option>
            <Option value="debug">Debug</Option>
          </Dropdown>
        </div>
        <Button icon={<ArrowSyncRegular />}>Refresh Logs</Button>
        <Button>Clear</Button>
      </div>
      
      <div className={styles.logsContainer}>
        {sampleLogs.map((log, index) => (
          <div
            key={index}
            className={`${styles.logEntry} ${
              log.level === 'error' ? styles.logError :
              log.level === 'warning' ? styles.logWarning :
              log.level === 'info' ? styles.logInfo : ''
            }`}
          >
            <span className={styles.logTime}>{log.time}</span>
            <span 
              className={styles.logLevel}
              style={{
                backgroundColor: 
                  log.level === 'error' ? '#f44336' :
                  log.level === 'warning' ? '#ff9800' :
                  log.level === 'info' ? '#4CAF50' : '#2196F3',
                color: 'white'
              }}
            >
              {log.level.toUpperCase()}
            </span>
            <span className={styles.logMessage}>{log.message}</span>
          </div>
        ))}
      </div>
    </>
  );

  // Render search view
  const renderSearchView = () => (
    <>
      <div className={styles.topBar}>
        <Text className={styles.searchHeader}>
          Semantic Search Across All Transcripts
        </Text>
      </div>
      
      <div className={styles.searchView}>
        <div className={styles.searchBox}>
          <Textarea
            placeholder="Ask a question or describe what you're looking for across all meeting transcripts...

Example: 'What did we decide about the Q4 budget?' or 'Find all discussions about customer retention'"
            value={ragQuery}
            onChange={(e, data) => setRagQuery(data.value)}
            rows={4}
            resize="vertical"
          />
          <Button
            appearance="primary"
            className={styles.searchButton}
            onClick={handleRAGSearch}
            size="large"
          >
            Search All Transcripts
          </Button>
        </div>
        
        <div className={styles.searchResults}>
          {ragResults.length > 0 ? (
            ragResults.map(result => (
              <div key={result.id} className={styles.searchResult}>
                <div className={styles.searchResultTitle}>{result.title}</div>
                <div className={styles.searchResultMeta}>
                  {result.date}  {result.speakers}  Relevance: {result.relevance}%
                </div>
                <div className={styles.searchResultSnippet}>{result.snippet}</div>
              </div>
            ))
          ) : (
            <Card>
              <Text align="center" size={300}>
                Enter a search query to find relevant content across all your meeting transcripts
              </Text>
            </Card>
          )}
        </div>
      </div>
    </>
  );

  return (
    <FluentProvider theme={webLightTheme}>
      <div className={styles.container}>
        {renderNavRail()}
        <div className={styles.mainContent}>
          {activeView === 'transcripts' && renderTranscriptsView()}
          {activeView === 'logs' && renderLogsView()}
          {activeView === 'search' && renderSearchView()}
        </div>
      </div>
    </FluentProvider>
  );
}
