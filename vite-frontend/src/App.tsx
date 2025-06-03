import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';

import { MantineProvider, AppShell, Group, rem } from '@mantine/core';
import { Router } from './Router';
import { theme } from './theme';
import { Notifications } from '@mantine/notifications';
import GlobalStyle from './GlobalStyle';
import { LocalAuthDropdown } from './components/LocalAuthDropdown';

export default function App() {
  return (
    <MantineProvider theme={theme}>
      <Notifications position="top-right" />
      <GlobalStyle />
      
      <AppShell
        header={import.meta.env.VITE_LOCAL_AUTH ? { height: { base: 60 } } : undefined}
        padding="md"
      >
        {import.meta.env.VITE_LOCAL_AUTH && (
          <AppShell.Header p="md">
            <Group justify="flex-end">
              <LocalAuthDropdown />
            </Group>
          </AppShell.Header>
        )}
        
        <AppShell.Main>
          <Router />
        </AppShell.Main>
      </AppShell>
    </MantineProvider>
  );
}
