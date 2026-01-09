export const APP_COLORS = {
  success: '#10B981',
  warning: '#F59E0B',
  danger: '#EF4444',
  info: '#3B82F6',
  transcriptSpeaker: '#2563EB',
  transcriptSpeakerSoft: '#6B7DB8',  // Softer speaker label color
  selectionBorder: '#4FC3F7',
  navRailBg: '#0078D4',
  listBackground: '#F5F5F5',  // Soft gray for list column
  cardBackground: '#FFFFFF',
  speaker1Bg: '#F0F7FF',  // Light blue tint for speaker 1
  speaker2Bg: '#F5F5F5',  // Light gray tint for speaker 2
  speaker1Border: '#3B82F6',  // Blue border for speaker 1
  speaker2Border: '#9CA3AF',  // Gray border for speaker 2
  iconMuted: '#9CA3AF',  // Muted icon color
  iconHover: '#374151',  // Darker icon on hover
} as const;

export const SPACING = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
} as const;

export const LAYOUT = {
  navRailWidth: 96,
  navRailExpandedWidth: 240,
  listPanelWidthPercent: 35,
} as const;
