import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import { HomePage } from './pages/Home.page';
import RecordingsPage from './pages/RecordingsPage';
import UploadPage from './pages/UploadPage';
import ViewTranscriptionPage from './pages/ViewTranscriptionPage';
import RecordingCardsPage from './pages/RecordingCardsPage';
const router = createBrowserRouter([
  {
    path: '/',
    element: <HomePage />,
  },
  {
    path: '/recordings',
    element: <RecordingCardsPage />,
  },
  {
    path: '/upload',
    element: <UploadPage />,
  },
  {
    path: '/view_transcription/:transcriptionId',
    element: <ViewTranscriptionPage />,
  },
]);

export function Router() {
  return <RouterProvider router={router} />;
}
