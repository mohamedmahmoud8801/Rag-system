import { useEffect } from "react";
import { Link } from "react-router-dom";
import { Loader2, MessageSquare, Play } from "lucide-react";
import { Page, PageHeader } from "@/components/layout/PageHeader";
import { Alert, Badge, Button, Card, Input } from "@/components/ui";
import { useI18n } from "@/i18n";
import { useVideo } from "@/hooks/video";
import { useData } from "@/hooks/data";

export default function Video() {
  const { t } = useI18n();
  const { addFile } = useData();
  const {
    url, setUrl, language, setLanguage, chunkSize, setChunkSize, overlap, setOverlap,
    result, loading, error, ingest,
  } = useVideo();

  useEffect(() => {
    if (result?.success && result?.asset_name) {
      addFile({ 
        file_id: result.asset_name, 
        name: `يوتيوب: ${result.video_id}`, 
        size: 0, 
        uploaded_at: Date.now() 
      });
    }
  }, [result, addFile]);

  return (
    <Page>
      <PageHeader title={t("video.title")} subtitle={t("video.subtitle")} />

      <Card className="p-5">
        <div className="space-y-3">
          <Input
            label={t("video.url")}
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            ltr
            placeholder="https://www.youtube.com/watch?v=..."
            disabled={loading}
          />
          <Input
            label={t("video.language")}
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            ltr
            placeholder="ar / en (optional)"
            disabled={loading}
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              label={t("data.chunkSize")}
              type="number"
              value={chunkSize}
              onChange={(e) => setChunkSize(+e.target.value)}
              ltr
              disabled={loading}
            />
            <Input
              label={t("data.overlapSize")}
              type="number"
              value={overlap}
              onChange={(e) => setOverlap(+e.target.value)}
              ltr
              disabled={loading}
            />
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <Button loading={loading} disabled={!url.trim() || loading} onClick={ingest}>
            <Play className="size-4" /> {t("video.ingest")}
          </Button>
          {loading && (
            <span className="inline-flex items-center gap-1.5 text-xs text-muted">
              <Loader2 className="size-3.5 animate-spin" />
              {t("video.processing")}
            </span>
          )}
        </div>

        {error && <div className="mt-3"><Alert>{error}</Alert></div>}
      </Card>

      {result && (
        <Card className="mt-4 p-5">
          <div className="mb-3 flex items-center gap-2">
            <Badge tone="success">{t("video.done")}</Badge>
            <span className="text-sm font-medium" dir="ltr">{result.video_id}</span>
          </div>
          <dl className="grid gap-2 text-sm sm:grid-cols-2">
            <Info label={t("video.duration")} value={result.duration ? `${Math.round(result.duration)}s` : "—"} />
            <Info label={t("video.segments")} value={String(result.transcript_segments)} />
            <Info label={t("video.chunks")} value={String(result.chunks_created)} />
            <Info label={t("video.asset")} value={result.asset_name} />
          </dl>
          <div className="mt-4 border-t border-border pt-3">
            <Link to="/chat" className="inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
              <MessageSquare className="size-4" /> {t("data.ask")}
            </Link>
          </div>
        </Card>
      )}
    </Page>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-medium" dir="ltr">{value}</dd>
    </div>
  );
}