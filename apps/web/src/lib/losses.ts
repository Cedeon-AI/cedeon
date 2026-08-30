import type { LossImportStatus, LossRowStatus } from "@/lib/api";
import { uploadLossImport } from "@/lib/api";

type Tone = "neutral" | "info" | "success" | "warning" | "danger";

const IMPORT_STATUS: Record<LossImportStatus, { label: string; tone: Tone }> = {
  uploaded: { label: "Uploaded", tone: "neutral" },
  mapped: { label: "Mapped", tone: "info" },
  validated: { label: "Validated", tone: "info" },
  committed: { label: "Committed", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
};

export function importStatus(status: LossImportStatus) {
  return IMPORT_STATUS[status] ?? { label: status, tone: "neutral" as Tone };
}

const ROW_TONE: Record<LossRowStatus, Tone> = {
  ok: "success",
  warning: "warning",
  error: "danger",
  skipped: "neutral",
};

export function rowTone(status: LossRowStatus): Tone {
  return ROW_TONE[status] ?? "neutral";
}

/** Upload a CSV. hey-api types the multipart field as `string`; the FormData
 * serializer accepts the File — the cast is a known generator quirk. */
export function uploadLossImportFile(file: File) {
  return uploadLossImport({ body: { file: file as unknown as string } });
}

// Header-name synonyms used to pre-fill the column mapping. The user always
// reviews and can override — this is a convenience, not a decision.
const SYNONYMS: Record<string, string[]> = {
  claim_id: ["claim", "claimid", "claimref", "claimnumber", "claimno", "reference", "ref"],
  loss_event_identifier: ["event", "eventid", "catastrophe", "cat", "occurrence", "lossevent"],
  date_of_loss: ["dateofloss", "lossdate", "dol", "dateloss", "occurrencedate", "eventdate"],
  reported_date: ["reported", "reporteddate", "datereported", "notified", "noticedate"],
  gross_paid: ["paid", "grosspaid", "paidloss", "paymentstodate", "amountpaid"],
  gross_case_reserve: ["reserve", "casereserve", "grosscasereserve", "outstanding", "os"],
  gross_incurred: ["incurred", "grossincurred", "totalincurred", "grossloss", "ultimate"],
  currency: ["currency", "ccy", "cur", "iso"],
  status: ["status", "claimstatus", "openclosed"],
  cause_of_loss: ["cause", "causeofloss", "peril", "lossperil", "causecode"],
  location: ["location", "locationdesc", "risklocation", "state", "county", "address"],
  description: ["description", "desc", "narrative", "notes", "lossdescription"],
};

const normalize = (value: string) => value.toLowerCase().replace(/[^a-z0-9]/g, "");

export function guessMapping(
  headerColumns: string[],
  canonicalFields: string[],
): Record<string, string> {
  const mapping: Record<string, string> = {};
  const takenColumns = new Set<string>();
  for (const field of canonicalFields) {
    const synonyms = SYNONYMS[field] ?? [normalize(field)];
    const match = headerColumns.find(
      (column) => !takenColumns.has(column) && synonyms.includes(normalize(column)),
    );
    if (match) {
      mapping[field] = match;
      takenColumns.add(match);
    }
  }
  return mapping;
}
