import { useIsAuthenticated, useMsal } from '@azure/msal-react';
import { Button, Menu, MenuTrigger, MenuPopover, MenuList, MenuItem, Avatar, makeStyles, tokens } from '@fluentui/react-components';
import { SignOut20Regular, Person20Regular } from '@fluentui/react-icons';
import { loginRequest, authEnabled } from '../../config/authConfig';

const useStyles = makeStyles({
  userButton: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  },
  userInfo: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
  },
  userName: {
    fontWeight: tokens.fontWeightSemibold,
    fontSize: tokens.fontSizeBase300,
  },
  userEmail: {
    fontSize: tokens.fontSizeBase200,
    color: tokens.colorNeutralForeground3,
  },
});

/**
 * AuthButton component
 *
 * Shows login button when not authenticated.
 * Shows user menu with logout when authenticated.
 * Only rendered when authentication is enabled.
 */
export function AuthButton() {
  const styles = useStyles();
  const isAuthenticated = useIsAuthenticated();
  const { instance, accounts } = useMsal();

  // Don't render anything if auth is disabled
  if (!authEnabled) {
    return null;
  }

  const handleLogin = () => {
    instance.loginRedirect(loginRequest);
  };

  const handleLogout = () => {
    instance.logoutRedirect({
      postLogoutRedirectUri: window.location.origin,
    });
  };

  // Not authenticated - show login button
  if (!isAuthenticated || accounts.length === 0) {
    return (
      <Button
        appearance="primary"
        icon={<Person20Regular />}
        onClick={handleLogin}
      >
        Sign In
      </Button>
    );
  }

  // Authenticated - show user menu
  const account = accounts[0];
  const displayName = account.name || account.username;
  const email = account.username;

  return (
    <Menu>
      <MenuTrigger>
        <Button appearance="subtle" className={styles.userButton}>
          <Avatar
            name={displayName}
            size={24}
            color="colorful"
          />
          <span>{displayName}</span>
        </Button>
      </MenuTrigger>

      <MenuPopover>
        <MenuList>
          <MenuItem disabled>
            <div className={styles.userInfo}>
              <div className={styles.userName}>{displayName}</div>
              <div className={styles.userEmail}>{email}</div>
            </div>
          </MenuItem>
          <MenuItem
            icon={<SignOut20Regular />}
            onClick={handleLogout}
          >
            Sign Out
          </MenuItem>
        </MenuList>
      </MenuPopover>
    </Menu>
  );
}
