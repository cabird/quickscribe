import { useState, useEffect } from 'react';
import {
  makeStyles,
  mergeClasses,
  Button,
  Tooltip,
  Text,
  tokens,
  Avatar,
  Menu,
  MenuTrigger,
  MenuPopover,
  MenuList,
  MenuItem,
} from '@fluentui/react-components';
import {
  DocumentText24Regular,
  TaskListLtr24Regular,
  Search24Regular,
  Settings24Regular,
  Pin24Regular,
  Pin24Filled,
  SignOut20Regular,
  Person24Regular,
  People24Regular,
  DocumentText20Regular,
  TaskListLtr20Regular,
  Search20Regular,
  Settings20Regular,
  People20Regular,
} from '@fluentui/react-icons';
import { useIsAuthenticated, useMsal } from '@azure/msal-react';
import { LAYOUT } from '../../config/styles';
import { versionService } from '../../services/versionService';
import { loginRequest, authEnabled } from '../../config/authConfig';
import { useIsMobile } from '../../hooks/useIsMobile';

const useStyles = makeStyles({
  // Desktop sidebar styles
  navRail: {
    flexShrink: 0,
    backgroundColor: tokens.colorNeutralBackground1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    paddingTop: '12px',
    paddingBottom: '12px',
    height: '100%',
    boxShadow: tokens.shadow8,
    transitionProperty: 'width',
    transitionDuration: '200ms',
    transitionTimingFunction: 'ease-in-out',
    overflow: 'hidden',
    zIndex: 100,
  },
  navRailCollapsed: {
    width: `${LAYOUT.navRailWidth}px`,
  },
  navRailExpanded: {
    width: `${LAYOUT.navRailExpandedWidth}px`,
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    paddingLeft: '12px',
    paddingRight: '8px',
    marginBottom: '16px',
    minHeight: '72px',
  },
  logo: {
    width: '72px',
    height: '72px',
    flexShrink: 0,
    objectFit: 'contain',
  },
  logoText: {
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase400,
    color: tokens.colorNeutralForeground1,
    marginLeft: '8px',
    whiteSpace: 'nowrap',
    opacity: 0,
    transitionProperty: 'opacity',
    transitionDuration: '200ms',
  },
  logoTextVisible: {
    opacity: 1,
  },
  pinButton: {
    marginLeft: 'auto',
    minWidth: '32px',
    width: '32px',
    height: '32px',
    opacity: 0,
    transitionProperty: 'opacity',
    transitionDuration: '200ms',
  },
  pinButtonVisible: {
    opacity: 1,
  },
  pinButtonActive: {
    color: tokens.colorBrandForeground1,
  },
  navItems: {
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    gap: '4px',
    paddingLeft: '8px',
    paddingRight: '8px',
  },
  navItem: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    height: '44px',
    paddingLeft: '10px',
    paddingRight: '10px',
    borderRadius: tokens.borderRadiusMedium,
    cursor: 'pointer',
    transitionProperty: 'background-color',
    transitionDuration: '150ms',
    border: 'none',
    backgroundColor: 'transparent',
    ':hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  navItemActive: {
    backgroundColor: tokens.colorBrandBackground,
    ':hover': {
      backgroundColor: tokens.colorBrandBackgroundHover,
    },
  },
  navIcon: {
    flexShrink: 0,
    color: tokens.colorNeutralForeground1,
    transform: 'scale(1.25)',
  },
  navIconActive: {
    color: tokens.colorNeutralForegroundOnBrand,
  },
  navLabel: {
    marginLeft: '12px',
    fontSize: tokens.fontSizeBase300,
    fontWeight: tokens.fontWeightRegular,
    color: tokens.colorNeutralForeground1,
    whiteSpace: 'nowrap',
    opacity: 0,
    transitionProperty: 'opacity',
    transitionDuration: '200ms',
  },
  navLabelVisible: {
    opacity: 1,
  },
  navLabelActive: {
    color: tokens.colorNeutralForegroundOnBrand,
    fontWeight: tokens.fontWeightSemibold,
  },
  spacer: {
    flexGrow: 1,
  },
  footer: {
    display: 'flex',
    flexDirection: 'column',
    width: '100%',
    paddingLeft: '8px',
    paddingRight: '8px',
    gap: '8px',
  },
  userSection: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    paddingLeft: '10px',
    paddingRight: '10px',
    height: '44px',
    borderRadius: tokens.borderRadiusMedium,
    cursor: 'pointer',
    ':hover': {
      backgroundColor: tokens.colorNeutralBackground1Hover,
    },
  },
  userInfo: {
    marginLeft: '12px',
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    opacity: 0,
    transitionProperty: 'opacity',
    transitionDuration: '200ms',
  },
  userInfoVisible: {
    opacity: 1,
  },
  userName: {
    fontSize: tokens.fontSizeBase300,
    fontWeight: tokens.fontWeightSemibold,
    color: tokens.colorNeutralForeground1,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  userEmail: {
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
  },
  version: {
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
    paddingLeft: '10px',
    textAlign: 'left',
    userSelect: 'text',
  },

  // Mobile bottom tab bar styles
  bottomBar: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-around',
    width: '100%',
    height: `${LAYOUT.mobileBottomBarHeight}px`,
    backgroundColor: tokens.colorNeutralBackground1,
    boxShadow: '0 -1px 3px rgba(0, 0, 0, 0.12)',
    flexShrink: 0,
    zIndex: 100,
    paddingBottom: 'env(safe-area-inset-bottom, 0px)',
  },
  bottomBarItem: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    flex: 1,
    height: '100%',
    border: 'none',
    backgroundColor: 'transparent',
    cursor: 'pointer',
    gap: '2px',
    padding: '4px 0',
    color: tokens.colorNeutralForeground3,
  },
  bottomBarItemActive: {
    color: tokens.colorBrandForeground1,
  },
  bottomBarLabel: {
    fontSize: '10px',
    lineHeight: '12px',
    whiteSpace: 'nowrap',
  },
});

interface NavItem {
  id: 'transcripts' | 'people' | 'logs' | 'search' | 'settings';
  icon: React.ReactElement;
  mobileIcon: React.ReactElement;
  label: string;
}

const navItems: NavItem[] = [
  { id: 'transcripts', icon: <DocumentText24Regular />, mobileIcon: <DocumentText20Regular />, label: 'Transcripts' },
  { id: 'people', icon: <People24Regular />, mobileIcon: <People20Regular />, label: 'People' },
  { id: 'logs', icon: <TaskListLtr24Regular />, mobileIcon: <TaskListLtr20Regular />, label: 'Jobs' },
  { id: 'search', icon: <Search24Regular />, mobileIcon: <Search20Regular />, label: 'Search' },
  { id: 'settings', icon: <Settings24Regular />, mobileIcon: <Settings20Regular />, label: 'Settings' },
];

interface NavigationRailProps {
  activeView: 'transcripts' | 'people' | 'logs' | 'search' | 'settings';
  onViewChange: (view: 'transcripts' | 'people' | 'logs' | 'search' | 'settings') => void;
}

export function NavigationRail({ activeView, onViewChange }: NavigationRailProps) {
  const styles = useStyles();
  const isMobile = useIsMobile();
  const [version, setVersion] = useState<string>('...');
  const [isHovering, setIsHovering] = useState(false);
  const [isPinned, setIsPinned] = useState(false);

  const isAuthenticated = useIsAuthenticated();
  const { instance, accounts } = useMsal();

  const isExpanded = isHovering || isPinned;

  useEffect(() => {
    versionService.getVersion().then(setVersion);
  }, []);

  const handleLogin = () => {
    if (authEnabled) {
      instance.loginRedirect(loginRequest);
    }
  };

  const handleLogout = () => {
    instance.logoutRedirect({
      postLogoutRedirectUri: window.location.origin,
    });
  };

  const account = accounts[0];
  const displayName = account?.name || account?.username || 'User';
  const email = account?.username || '';

  // Mobile bottom tab bar
  if (isMobile) {
    return (
      <div className={styles.bottomBar}>
        {navItems.map((item) => {
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              className={mergeClasses(
                styles.bottomBarItem,
                isActive && styles.bottomBarItemActive
              )}
              onClick={() => onViewChange(item.id)}
            >
              {item.mobileIcon}
              <span className={styles.bottomBarLabel}>{item.label}</span>
            </button>
          );
        })}
      </div>
    );
  }

  // Desktop sidebar
  const renderNavItem = (item: NavItem) => {
    const isActive = activeView === item.id;

    const button = (
      <button
        key={item.id}
        className={mergeClasses(
          styles.navItem,
          isActive && styles.navItemActive
        )}
        onClick={() => onViewChange(item.id)}
      >
        <span className={mergeClasses(styles.navIcon, isActive && styles.navIconActive)}>
          {item.icon}
        </span>
        <span
          className={mergeClasses(
            styles.navLabel,
            isExpanded && styles.navLabelVisible,
            isActive && styles.navLabelActive
          )}
        >
          {item.label}
        </span>
      </button>
    );

    if (!isExpanded) {
      return (
        <Tooltip key={item.id} content={item.label} relationship="label" positioning="after">
          {button}
        </Tooltip>
      );
    }

    return button;
  };

  const renderUserSection = () => {
    const userContent = (
      <div className={styles.userSection}>
        <Avatar
          name={isAuthenticated && account ? displayName : undefined}
          icon={!isAuthenticated || !account ? <Person24Regular /> : undefined}
          size={32}
          color="colorful"
        />
        <div className={mergeClasses(styles.userInfo, isExpanded && styles.userInfoVisible)}>
          <Text className={styles.userName}>
            {isAuthenticated && account ? displayName : 'Guest'}
          </Text>
          {isAuthenticated && account && email && (
            <Text className={styles.userEmail}>{email}</Text>
          )}
        </div>
      </div>
    );

    // If auth is enabled and user is authenticated, show menu with logout
    if (authEnabled && isAuthenticated && account) {
      return (
        <Menu>
          <MenuTrigger disableButtonEnhancement>
            {userContent}
          </MenuTrigger>
          <MenuPopover>
            <MenuList>
              <MenuItem disabled>
                <div>
                  <div style={{ fontWeight: 600 }}>{displayName}</div>
                  <div style={{ fontSize: '12px', color: tokens.colorNeutralForeground3 }}>{email}</div>
                </div>
              </MenuItem>
              <MenuItem icon={<SignOut20Regular />} onClick={handleLogout}>
                Sign Out
              </MenuItem>
            </MenuList>
          </MenuPopover>
        </Menu>
      );
    }

    // If auth is enabled but not authenticated, clicking logs in
    if (authEnabled && !isAuthenticated) {
      const clickableContent = (
        <div className={styles.userSection} onClick={handleLogin} role="button" tabIndex={0}>
          <Avatar
            icon={<Person24Regular />}
            size={32}
            color="colorful"
          />
          <div className={mergeClasses(styles.userInfo, isExpanded && styles.userInfoVisible)}>
            <Text className={styles.userName}>Sign In</Text>
          </div>
        </div>
      );

      if (!isExpanded) {
        return (
          <Tooltip content="Sign In" relationship="label" positioning="after">
            {clickableContent}
          </Tooltip>
        );
      }
      return clickableContent;
    }

    // Auth disabled - just show placeholder
    if (!isExpanded) {
      return (
        <Tooltip content="Guest" relationship="label" positioning="after">
          {userContent}
        </Tooltip>
      );
    }
    return userContent;
  };

  return (
    <div
      className={mergeClasses(
        styles.navRail,
        isExpanded ? styles.navRailExpanded : styles.navRailCollapsed
      )}
      onMouseEnter={() => setIsHovering(true)}
      onMouseLeave={() => setIsHovering(false)}
    >
      {/* Header with logo and pin */}
      <div className={styles.header}>
        <img src="/quickscribe-icon.png" alt="QuickScribe" className={styles.logo} />
        <Text className={mergeClasses(styles.logoText, isExpanded && styles.logoTextVisible)}>
          QuickScribe
        </Text>
        <Tooltip content={isPinned ? 'Unpin sidebar' : 'Pin sidebar'} relationship="label">
          <Button
            appearance="subtle"
            icon={isPinned ? <Pin24Filled /> : <Pin24Regular />}
            className={mergeClasses(
              styles.pinButton,
              isExpanded && styles.pinButtonVisible,
              isPinned && styles.pinButtonActive
            )}
            onClick={() => setIsPinned(!isPinned)}
          />
        </Tooltip>
      </div>

      {/* Navigation items */}
      <div className={styles.navItems}>
        {navItems.map(renderNavItem)}
      </div>

      <div className={styles.spacer} />

      {/* Footer with user and version */}
      <div className={styles.footer}>
        {renderUserSection()}
        <Tooltip content={`API Version: ${version}`} relationship="label" positioning="after">
          <Text className={styles.version}>v{version}</Text>
        </Tooltip>
      </div>
    </div>
  );
}
