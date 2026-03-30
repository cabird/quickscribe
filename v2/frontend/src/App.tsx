import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ToastContainer } from "react-toastify";
import "react-toastify/dist/ReactToastify.css";

import { Layout } from "@/components/layout/Layout";
import RecordingsPage from "@/pages/RecordingsPage";

import PeoplePage from "@/pages/PeoplePage";
import JobsPage from "@/pages/JobsPage";
import SettingsPage from "@/pages/SettingsPage";
import SearchPage from "@/pages/SearchPage";
import CollectionsPage from "@/pages/CollectionsPage";
import SpeakerReviewsPage from "@/pages/SpeakerReviewsPage";

// ---------------------------------------------------------------------------
// TanStack Query client
// ---------------------------------------------------------------------------

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000, // 30 seconds
      retry: 1,
      refetchOnWindowFocus: true,
    },
  },
});

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<Navigate to="/recordings" replace />} />
              <Route path="recordings" element={<RecordingsPage />} />
              <Route path="recordings/:id" element={<RecordingsPage />} />
              <Route path="reviews" element={<SpeakerReviewsPage />} />
              <Route path="people" element={<PeoplePage />} />
              <Route path="people/:id" element={<PeoplePage />} />
              <Route path="jobs" element={<JobsPage />} />
              <Route path="jobs/:id" element={<JobsPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="search" element={<SearchPage />} />
              <Route path="collections" element={<CollectionsPage />} />
              <Route path="collections/:id" element={<CollectionsPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <ToastContainer
          position="bottom-right"
          autoClose={4000}
          hideProgressBar
          newestOnTop
          closeOnClick
          pauseOnFocusLoss={false}
          theme="colored"
        />
      </TooltipProvider>
    </QueryClientProvider>
  );
}
