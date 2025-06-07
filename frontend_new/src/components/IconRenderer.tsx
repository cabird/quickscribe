import { ICON_LIBRARY, type IconName } from '../constants/iconLibrary';
import { LuX } from 'react-icons/lu';

interface IconRendererProps {
  iconName: string;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Renders a Lucide icon by name with fallback to default icon
 * Simple and straightforward - no complex error handling
 */
export function IconRenderer({ iconName, size = 24, className, style }: IconRendererProps) {
  // Get the icon component from the library
  const IconComponent = ICON_LIBRARY[iconName as IconName];
  
  // If icon doesn't exist, use a default X icon
  const FinalIcon = IconComponent || LuX;
  
  return (
    <FinalIcon 
      size={size} 
      className={className}
      style={style}
    />
  );
}