import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';

import { MantineProvider } from '@mantine/core';
import { Router } from './Router';
import { theme } from './theme';
import { Notifications, notifications } from '@mantine/notifications';
import GlobalStyle from './GlobalStyle';

export default function App() {
  return (

    <MantineProvider theme={theme}>
      <Notifications position="top-right" />
      <GlobalStyle />
      <Router />

    </MantineProvider>
  );
}
