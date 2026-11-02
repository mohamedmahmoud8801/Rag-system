import "@fontsource-variable/geist";
import "@fontsource/ibm-plex-sans-arabic/400.css";
import "@fontsource/ibm-plex-sans-arabic/500.css";
import "@fontsource/ibm-plex-sans-arabic/600.css";
import "./index.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { AuthProvider } from "./hooks/auth";
import { ProjectProvider } from "./hooks/project";
import { ChatProvider } from "./hooks/chat";
import { DataProvider } from "./hooks/data";
import { KnowledgeProvider } from "./hooks/knowledge";
import { EvaluationProvider } from "./hooks/evaluation";
import { VideoProvider } from "./hooks/video";
import { DatabasesProvider } from "./hooks/databases";
import { LanguageProvider } from "./i18n";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <LanguageProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ProjectProvider>
            <ChatProvider>
              <DataProvider>
                <KnowledgeProvider>
                  <EvaluationProvider>
                    <VideoProvider>
                      <DatabasesProvider>
                        <App />
                      </DatabasesProvider>
                    </VideoProvider>
                  </EvaluationProvider>
                </KnowledgeProvider>
              </DataProvider>
            </ChatProvider>
          </ProjectProvider>
        </AuthProvider>
      </QueryClientProvider>
    </LanguageProvider>
  </StrictMode>,
);