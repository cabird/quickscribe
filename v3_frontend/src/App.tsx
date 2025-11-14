import { FluentProvider } from '@fluentui/react-components';
import { ToastContainer } from 'react-toastify';
import { lightTheme } from './theme/customTheme';
import { MainLayout } from './components/layout/MainLayout';
import './styles/globals.css';
import 'react-toastify/dist/ReactToastify.css';

function App() {
  return (
    <FluentProvider theme={lightTheme} style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <MainLayout />
      <ToastContainer
        position="top-right"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme="light"
      />
    </FluentProvider>
  );
}

export default App;
