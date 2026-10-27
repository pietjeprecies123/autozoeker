import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import { Spinner } from "./components/ui";
import "./index.css";
import { AppProvider } from "./lib/store";
import SearchPage from "./pages/SearchPage";

const ListingPage = lazy(() => import("./pages/ListingPage"));
const ChecklistPage = lazy(() => import("./pages/ChecklistPage"));
const ComparePage = lazy(() => import("./pages/ComparePage"));
const ForYouPage = lazy(() => import("./pages/ForYouPage"));
const WatchlistPage = lazy(() => import("./pages/WatchlistPage"));
const SavedSearchesPage = lazy(() => import("./pages/SavedSearchesPage"));
const MarketPage = lazy(() => import("./pages/MarketPage"));
const KentekenPage = lazy(() => import("./pages/KentekenPage"));
const IssuesPage = lazy(() => import("./pages/IssuesPage"));
const StatusPage = lazy(() => import("./pages/StatusPage"));

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, refetchOnWindowFocus: false, retry: 1 } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppProvider>
          <Layout>
            <Suspense fallback={<Spinner />}>
              <Routes>
                <Route path="/" element={<SearchPage />} />
                <Route path="/auto/:id" element={<ListingPage />} />
                <Route path="/auto/:id/checklist" element={<ChecklistPage />} />
                <Route path="/vergelijk" element={<ComparePage />} />
                <Route path="/voor-jou" element={<ForYouPage />} />
                <Route path="/favorieten" element={<WatchlistPage />} />
                <Route path="/zoekopdrachten" element={<SavedSearchesPage />} />
                <Route path="/markt" element={<MarketPage />} />
                <Route path="/kenteken" element={<KentekenPage />} />
                <Route path="/kenteken/:plate" element={<KentekenPage />} />
                <Route path="/aandachtspunten" element={<IssuesPage />} />
                <Route path="/aandachtspunten/:make/:model" element={<IssuesPage />} />
                <Route path="/status" element={<StatusPage />} />
                <Route path="*" element={<div className="py-20 text-center text-slate-500">Pagina niet gevonden</div>} />
              </Routes>
            </Suspense>
          </Layout>
        </AppProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
);
