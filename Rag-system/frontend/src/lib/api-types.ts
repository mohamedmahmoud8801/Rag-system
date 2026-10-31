export interface UploadResponse { signal: string; file_id?: string; }

export interface ProcessRequest {
  file_id?: string | null;
  chunk_size?: number;
  overlap_size?: number;
  do_reset?: number;
}
export interface ProcessResponse {
  signal: string;
  inserted_chunks?: number;
  processed_files?: number;
}

export interface IndexPushResponse { signal: string; inserted_items_count?: number; }
export interface IndexInfoResponse { signal: string; collection_info: unknown; }

export interface ExcelIngestResult {
  file_id: string;
  database_url: string;
  tables_created: number;
  total_rows_inserted: number;
  tables: {
    sheet_name: string;
    table_name: string;
    inserted_rows: number;
    replaced: boolean;
    columns: { original_name: string; name: string; type: string }[];
  }[];
}
export interface ExcelIngestResponse { success: boolean; result: ExcelIngestResult; }

export interface ExcelDB extends ExcelIngestResult { ingested_at: number; }

export interface DBConnection {
  id: string;
  name: string;
  provider: string;
  display?: string;
  url?: string;
  database_url?: string;
  meta?: Record<string, unknown>;
  table_count?: number;
  tables?: string[];
  [k: string]: unknown;
}

export interface DBTestResponse {
  ok: boolean;
  error?: string;
  provider?: string;
  display?: string;
  table_count?: number;
  tables?: string[];
}
export interface DBCreateResponse { success: boolean; connection: DBConnection; }
export interface DBListResponse { success: boolean; connections: DBConnection[]; }

export interface SqlQueryResponse {
  success: boolean;
  result: {
    question: string;
    sql: string;
    result: { columns?: string[]; rows?: Record<string, unknown>[]; row_count?: number };
    schema: unknown;
    attempts: number;
    errors: unknown[];
    verified?: boolean | null;
    warning?: string;
  };
}

export interface SqlExecuteResponse {
  success: boolean;
  result: {
    sql: string;
    result: unknown;
    columns: string[];
    rows: Record<string, unknown>[];
    row_count: number;
  };
}

export interface VideoIngestResponse {
  success: boolean;
  video_id: string;
  video_url: string;
  provider: string;
  source_type: string;
  language: string | null;
  duration: number | null;
  transcript_segments: number;
  asset_id: number;
  asset_name: string;
  chunks_created: number;
  chunk_ids: number[];
  collection_name: string;
}