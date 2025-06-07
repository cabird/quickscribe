import '@mantine/core/styles.css';
import '@mantine/notifications/styles.css';
import '@mantine/dropzone/styles.css';

import { MantineProvider, createTheme } from '@mantine/core';
import { Notifications } from '@mantine/notifications';
import { BrowserRouter } from 'react-router-dom';
import { AppLayout } from './components/Layout/AppLayout';

const theme = createTheme({
  primaryColor: 'blue',
  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  headings: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
  },
  components: {
    Button: {
      defaultProps: {
        variant: 'filled',
      },
      styles: (theme, params) => ({
        root: {
          backdropFilter: 'blur(16px)',
          borderRadius: '12px',
          transition: 'all 0.3s ease',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          // Only apply glass background for buttons without explicit color
          ...(!params.color ? {
            background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0.05))',
          } : {}),
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: '0 8px 32px rgba(0, 0, 0, 0.15)',
            // Only apply glass hover for buttons without explicit color
            ...(!params.color ? {
              background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.25), rgba(255, 255, 255, 0.1))',
            } : {}),
          },
        },
      }),
    },
    Card: {
      styles: {
        root: {
          background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.15), rgba(255, 255, 255, 0.05))',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.2)',
          borderRadius: '16px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
          transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
          '&:hover': {
            transform: 'translateY(-4px)',
            boxShadow: '0 16px 48px rgba(0, 0, 0, 0.15)',
            borderColor: 'rgba(255, 255, 255, 0.3)',
          },
        },
      },
    },
    Modal: {
      styles: {
        content: {
          background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.9), rgba(255, 255, 255, 0.85))',
          backdropFilter: 'blur(24px)',
          border: '1px solid rgba(255, 255, 255, 0.3)',
          borderRadius: '20px',
          boxShadow: '0 16px 64px rgba(0, 0, 0, 0.2)',
        },
        overlay: {
          backdropFilter: 'blur(8px)',
          background: 'rgba(0, 0, 0, 0.4)',
        },
      },
    },
    Paper: {
      styles: {
        root: {
          background: 'linear-gradient(135deg, rgba(255, 255, 255, 0.12), rgba(255, 255, 255, 0.06))',
          backdropFilter: 'blur(16px)',
          border: '1px solid rgba(255, 255, 255, 0.15)',
          borderRadius: '12px',
          boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
        },
      },
    },
  },
});

function App() {
  return (
    <MantineProvider theme={theme}>
      <Notifications position="top-right" />
      <BrowserRouter>
        <AppLayout />
      </BrowserRouter>
    </MantineProvider>
  );
}

export default App
