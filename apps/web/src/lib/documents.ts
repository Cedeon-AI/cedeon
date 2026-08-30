import type { DocumentKind, DocumentStatus } from "@/lib/api";
import { uploadDocument } from "@/lib/api";

const STATUS_TONE: Record<DocumentStatus, "neutral" | "info" | "success" | "danger"> = {
  uploaded: "neutral",
  parsing: "info",
  parsed: "success",
  parse_failed: "danger",
};

const STATUS_LABEL: Record<DocumentStatus, string> = {
  uploaded: "Uploaded",
  parsing: "Parsing…",
  parsed: "Parsed",
  parse_failed: "Parse failed",
};

export function statusTone(status: DocumentStatus) {
  return STATUS_TONE[status];
}

export function statusLabel(status: DocumentStatus) {
  return STATUS_LABEL[status];
}

export function isProcessing(status: DocumentStatus) {
  return status === "uploaded" || status === "parsing";
}

/** Upload a file. hey-api types the multipart field as `string`; the FormData
 * serializer accepts the File — the cast is a known generator quirk. */
export function uploadDocumentFile(file: File, kind: DocumentKind) {
  return uploadDocument({ body: { file: file as unknown as string, kind } });
}
