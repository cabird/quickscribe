import {
  // All icons verified from react-icons/lu/index.d.ts
  LuActivity,
  LuCheck,
  LuClock,
  LuCopy,
  LuDownload,
  LuEye,
  LuEyeOff,
  LuFile,
  LuFileText,
  LuGrid3X3,
  LuList,
  LuListTodo,
  LuMic,
  LuMusic,
  LuPencil,
  LuPlus,
  LuRefreshCw,
  LuSearch,
  LuSettings,
  LuTrash2,
  LuUpload,
  LuUser,
  LuUsers,
  LuX,
  
  // Additional useful icons that exist
  LuBrain,
  LuDatabase,
  LuFolder,
  LuHeart,
  LuStar,
  LuTarget,
  LuZap,
  LuMessageSquare,
  LuMail,
  LuCalendar,
  LuMapPin,
  LuGlobe,
  LuShield,
  LuAward,
  LuCrown,
  LuLightbulb,
  LuCode,
  LuLink,
  LuBook,
  LuClipboard,
  LuTag,
  LuTags,
  LuShare,
  LuPlay,
  LuPause,
  LuVolume2,
  LuThumbsUp,
  LuSmile,
  LuFrown,
  LuMeh,
  LuCircleHelp,
} from 'react-icons/lu';

/**
 * Comprehensive icon library with verified Lucide icons
 * All icons confirmed to exist in react-icons/lu v5.5.0
 */
export const ICON_LIBRARY = {
  // Document & File
  'file': LuFile,
  'file-text': LuFileText,
  'folder': LuFolder,
  'clipboard': LuClipboard,
  'book': LuBook,
  
  // Analysis & AI
  'brain': LuBrain,
  'database': LuDatabase,
  'search': LuSearch,
  'activity': LuActivity,
  'target': LuTarget,
  'zap': LuZap,
  
  // Lists & Organization
  'list': LuList,
  'list-todo': LuListTodo,
  'tag': LuTag,
  'tags': LuTags,
  'grid-3x3': LuGrid3X3,
  
  // Communication & Social
  'message-square': LuMessageSquare,
  'mail': LuMail,
  'mic': LuMic,
  'music': LuMusic,
  'volume-2': LuVolume2,
  
  // Emotions & Sentiment
  'heart': LuHeart,
  'star': LuStar,
  'smile': LuSmile,
  'frown': LuFrown,
  'meh': LuMeh,
  'thumbs-up': LuThumbsUp,
  
  // Actions & Tools
  'pencil': LuPencil,
  'copy': LuCopy,
  'share': LuShare,
  'download': LuDownload,
  'upload': LuUpload,
  'refresh-cw': LuRefreshCw,
  'trash-2': LuTrash2,
  'check': LuCheck,
  'plus': LuPlus,
  'x': LuX,
  
  // Time & Location
  'clock': LuClock,
  'calendar': LuCalendar,
  'map-pin': LuMapPin,
  'globe': LuGlobe,
  
  // People & Status
  'user': LuUser,
  'users': LuUsers,
  'crown': LuCrown,
  'award': LuAward,
  'shield': LuShield,
  
  // Media & Controls
  'play': LuPlay,
  'pause': LuPause,
  
  // Interface & Utility
  'eye': LuEye,
  'eye-off': LuEyeOff,
  'lightbulb': LuLightbulb,
  'settings': LuSettings,
  'code': LuCode,
  'link': LuLink,
  
  // Help & Questions
  'circle-help': LuCircleHelp,
} as const;

export type IconName = keyof typeof ICON_LIBRARY;

/**
 * Get all available icon names for selection interfaces
 */
export const getAvailableIcons = (): IconName[] => {
  return Object.keys(ICON_LIBRARY) as IconName[];
};

/**
 * Check if an icon name exists in the library
 */
export const isValidIcon = (iconName: string): iconName is IconName => {
  return iconName in ICON_LIBRARY;
};