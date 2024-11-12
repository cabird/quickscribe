import '@mantine/core/styles.css';

import { MantineProvider } from '@mantine/core';
import { Router } from './Router';
import { theme } from './theme';
import { Notifications } from '@mantine/notifications';
import GlobalStyle from './GlobalStyle';

export default function App() {
  return (

    <MantineProvider theme={theme}>
      <GlobalStyle />
      <Notifications />
      <Router />
    </MantineProvider>
  );
}
