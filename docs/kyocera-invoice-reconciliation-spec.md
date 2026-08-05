# Kyocera Invoice Reconciliation — Product Spec (for Lovable)

## 1. What this app is

A replacement for an old "Cromwell system" dashboard used to reconcile **vending-machine tooling stock** purchased from Kyocera Unimerco. Each period, three documents need to be checked against each other and against a discounted price list before the invoice is approved for payment:

1. **Invoice** (PDF, from Kyocera)
2. **Order Confirmation** (PDF, from Kyocera)
3. **Vend Report** (Excel, exported from the vending machine — this is the source of truth for what was actually taken)

A fourth document type, the **Price List** (Excel, from Kyocera, with a negotiated discount applied), is used to verify the invoice's unit prices are correct. It is managed independently of any single reconciliation and updated periodically.

The core value: today this three-way check takes a trained person ~2 minutes per session doing it by eye. The app should make that faster and auditable, not necessarily fully automatic — a manual price-check-then-approve step is expected to remain.

## 2. Users

Single internal team (procurement/finance admin, e.g. "Simon" and colleagues). No evidence of multiple customer-facing roles is needed — build for one authenticated internal team, but keep an `actor`/`created_by` field on everything for audit purposes in case roles are split later.

## 3. Core workflow

```
Create session (named, dated)
   -> Upload Invoice PDF, Vend Report (.xls/.xlsx), Order Confirmation PDF
      [optional: Delivery Note PDF — rarely useful, kept for reference only]
   -> System parses each document and auto-matches line items across all three
   -> Exception report generated (missing items, quantity mismatches, price
      mismatches, unreadable/unparsed lines)
   -> Manual price verification: reviewer checks invoice unit prices line-by-line
      against the active (discounted) Price List, resolves/annotates exceptions
   -> Approve session (locks it — no further edits, no delete)
   -> Optional: generate a customizable PDF report of what was checked
```

Sessions are never deleted — only created, matched, checked, and approved. Historical sessions remain browsable and re-openable for audit.

## 4. Data model

### 4.1 Reconciliation sessions

**`sessions`**
| field | type | notes |
|---|---|---|
| id | uuid | |
| name | text | user-defined, e.g. "WSF Vend 09.07–12.07" |
| vendor | text | default "Kyocera Unimerco"; keep as a field, not hardcoded, so other vendors can be added later |
| period_start / period_end | date | matches the "Your Reference" date range Kyocera prints on the order confirmation (e.g. `09.07-12.07`) |
| status | enum | `draft` → `matched` → `price_checked` → `approved` |
| created_by, created_at | | |
| approved_by, approved_at | nullable | |

**`documents`**
| field | type | notes |
|---|---|---|
| id | uuid | |
| session_id | fk | |
| doc_type | enum | `invoice`, `order_confirmation`, `vend_report`, `delivery_note` |
| original_filename, storage_path | | original file, always retained |
| is_secured_pdf | bool | see §7 |
| converted_storage_path | nullable | the Word→PDF re-export, if one was uploaded |
| parse_status | enum | `pending`, `parsed`, `partial`, `failed` |
| uploaded_by, uploaded_at | | |

Line items extracted from each document type get their own table so raw parses are preserved even if later re-matched:

Invoice header fields to capture on `documents` (or a small `invoice_header` extension): invoice_number, invoice_date, due_date, delivery_note_no (e.g. `5139526-0` — this is the order number plus a suffix, and is the field that most directly links an invoice back to its order confirmation), order_no, net_total, vat_total, total_due.

**`invoice_lines`** — item_no, description, spec_code, quantity, unit, unit_price, discount_pct, net_price, nominal_code (nullable, filled during price check)

**`order_confirmation_lines`** — order_no, item_no, description, spec_code, quantity, unit, unit_price, discount_pct, net_price, shipping_date

**`vend_report_lines`** — item_no (aka "Supplno."), spec_code, description, transaction_count, quantity_taken (store as positive; source data is negative because it's stock leaving the machine), amount
**`vend_report_transactions`** (child of a vend_report_line) — location_code (machine bin, e.g. `15L-07`), transaction_date, transaction_time, transaction_type (`I` = issue, etc.), quantity, unit_price, badge_no, amount — kept for drill-down/audit even though matching happens at the aggregated line level

### 4.2 Price list

**`price_lists`** — id, vendor, version_number, source_type (`incremental_add` | `full_replace` | `manual_edit`), status (`draft`|`active`|`archived`), effective_date, replaced_price_list_id (nullable, self-fk for rollback chain), uploaded_by, uploaded_at, notes

**`price_list_items`** — id, price_list_id, item_number, cust_item_name, spec_text, price_before_discount (nullable), discount_pct (nullable), current_price, new_price (nullable, with an effective_date), increase_amount (computed: new − current), nominal_code, is_manual_edit (bool)

Only one `price_lists` row is `active` at a time; it is the one used for price verification. Uploading a **full replacement** creates a new version and archives the previous one (with rollback = re-activating an archived version). **Incremental additions** append/update rows within the currently active list without creating a whole new version — but still snapshot the prior state so a specific addition can be undone. Individual items must be editable inline (price, nominal code) without going through a full re-upload, matching the real-world need for one-off corrections (e.g. Simon correcting a coding error).

### 4.3 Matching & exceptions

**`match_results`** — id, session_id, item_key (matched item/spec code), status (`matched`|`missing_in_invoice`|`missing_in_vend_report`|`missing_in_order_confirmation`|`quantity_mismatch`|`price_mismatch_docs`|`price_mismatch_pricelist`|`unreadable`), invoice_qty/price, order_conf_qty/price, vend_qty/amount, pricelist_price, delta, resolved (bool), resolved_by, resolved_at, notes

**`audit_log`** — session_id, actor, action, timestamp, details (json) — every upload, match run, manual override, price-check tick, and approval gets logged here; this is the backbone of the "no delete, full history" requirement.

### 4.4 Reports

**`reports`** — id, session_id, generated_by, generated_at, storage_path, included_sections (json: which of price-check / vend-report / order-confirmation summaries to include)

## 5. Matching logic (business rules)

1. **Item identity across documents**: primary match key is the vendor item/product code (e.g. `ISC5592941`). Kyocera's own numbering is reasonably consistent across invoice/order-confirmation/vend-report in the sample data, so exact match should be tried first; fall back to normalized spec-code text match (strip whitespace/case) only when exact match fails, and flag those as lower-confidence matches for manual review rather than silently accepting them.
1a. **Header-level cross-check, before line matching**: the invoice's `Order No.` (and its `Delivery Note No.`, which is the order number plus a suffix, e.g. `5139526-0`) should equal the order confirmation's `Order No.`. If a session's uploaded invoice and order confirmation don't share an order number, raise a session-level exception immediately rather than proceeding to line-level matching — this catches the case where the wrong pair of documents was uploaded to a session.
2. **Three-way match** passes when, for a given item: quantity is equal across invoice, order confirmation, and vend report (vend report quantities are negative in the source file — treat magnitude as quantity taken), and the invoice's net price for that line equals the order confirmation's net price for that line.
3. **Price-list check** is separate from the three-way match: invoice unit price (before the line discount shown on the invoice) is compared to the **active price list's** `current_price` (or `new_price` if today is past its effective date) for that item number. Flag if the delta exceeds a small tolerance (configurable, default £0.01 or 0.5%, whichever is greater) — this check stays a manual "tick to confirm" step even when the system finds no discrepancy, per the required workflow (auto-match, then pause for manual price check, then approve).
4. **Exception types to surface**: missing item (present in one/two docs but not all three), quantity mismatch, price mismatch (between the three docs), price-list mismatch (invoice vs. discounted list), unreadable/unparsed line (PDF or Excel row the parser couldn't confidently extract — never silently drop a row, always surface it as an exception needing manual entry/confirmation).
5. **Delivery notes** are out of scope for matching. If one is uploaded, store it against the session for reference only; do not include it in the auto-match or exception logic.
6. **Returns/credits**: no evidence of negative-quantity returns in current vend reports (unlike the old Cromwell system). Don't build a returns/refund workflow yet — just make sure a negative net amount on an invoice line doesn't crash the matcher; flag it as an exception for manual review instead of guessing at return handling.

## 6. Screens

1. **Dashboard** — list of sessions (name, date range, status badge, last updated), "New session" button, search/filter by status or date. No delete action anywhere on this screen or session detail — only create/edit-until-approved.
2. **Session detail / upload** — three (or four, with delivery note) upload slots clearly labeled Invoice / Order Confirmation / Vend Report / (optional) Delivery Note, each accepting the right file type (PDF for invoice/order-conf/delivery-note, .xls/.xlsx for vend report). Shows parse status per document. A "Run matching" action once all required docs are uploaded.
3. **Exceptions view** — table of `match_results`, grouped by exception type, filterable, each row expandable to show the raw values from each source document side by side. Ability to mark an exception resolved with a note (does not change source data — it's an audit annotation).
4. **Price verification view** — invoice lines listed against the active price list's discounted price, line-by-line, with a checkbox/"confirmed" state per line and inline flags where price doesn't match; nominal code shown/editable per line so job-costing allocation can happen inline. Session cannot move to `approved` until every invoice line is either confirmed or explicitly annotated.
5. **Approve** — a single confirmation action once matching + price check are complete; sets status to `approved`, locks the session (read-only from here on), stamps approved_by/approved_at.
6. **Price list management** — table view of the active price list (columns matching the source file: Item Number, Description, Spec, Price Before Discount, Discount %, Current Price, New Price + effective date, Increase, Nominal Code). Actions: **Add items** (upload a small incremental file or add rows manually — mirrors the vendor's "Vend editions" update pattern), **Replace price list** (upload a full new file, show a diff/preview of what will change before confirming, archive the old version), **Edit item** (inline edit of price/nominal code on a single row), **Version history** with a "Rollback to this version" action per past version.
7. **Reports** — from an approved session, generate a PDF report; let the user pick which sections to include (price-check summary, exceptions summary, per-document line detail); download and/or view previously generated reports for that session.

## 7. Handling secured/protected Kyocera PDFs

Kyocera's invoice/order-confirmation PDFs are sometimes locked against copy/edit, so today the team manually re-creates them (copy into Word, save as a new PDF) to annotate/attach. The app should:

- Accept the **original secured PDF** as the primary uploaded document (always retained for audit).
- Also accept an optional **converted PDF** (the Word round-trip output) uploaded separately against the same document slot, used for annotation/highlighting and as the parsing source when the original can't be read programmatically.
- Attempt text extraction from the original first; if extraction fails or returns clearly incomplete data, mark `parse_status = failed` and prompt the user to supply the converted version instead of blocking the workflow.
- This is explicitly a workaround, not a solved problem — the spec should leave room to revisit automated extraction once more secured-PDF samples are available (see open questions).

## 8. Reporting, storage, backup

- Every session's raw uploaded files, parsed line items, match results, and audit log persist indefinitely (no delete).
- Generated reports are stored PDFs tied to a session, re-downloadable at any time, not regenerated-in-place (each generation is a new `reports` row so historical reports aren't silently changed by later data edits — though sessions are locked after approval anyway).
- Note in the spec for whoever configures hosting: this data needs a real backup/export policy (e.g. scheduled DB export + file storage versioning) — flag it as an infra task, not just an app feature, since the source material calls this out as something still being scoped with the vendor rather than a settled requirement.

## 9. Non-functional requirements

- Single internal login (email/password is sufficient); every mutating action records an actor.
- Sessions and price lists are the two things that must never silently lose history — enforce "no hard delete" at the data layer, not just hidden in the UI.
- Tolerant parsing: a document with an unreadable line should degrade to "flag for manual entry," never to silently dropping or silently guessing a value.
- Reasonably fast: matching a session's three documents should complete in well under the ~2 minutes the manual process takes today, with the manual price-check step being the deliberately-kept-manual bottleneck, not parsing speed.

## 10. Suggested tech approach (Lovable defaults)

- React + Tailwind + shadcn/ui frontend, Supabase for Postgres, auth, file storage, and edge functions — Lovable's standard stack, and a good fit here (relational data, file uploads, row-level audit trail).
- Excel parsing (`.xls` and `.xlsx`) client-side or in an edge function using a library like `xlsx`/`sheetjs`; the vend report is **not** a flat table (see §11 appendix) — it has a summary row per item followed by indented transaction detail rows — so the parser needs to walk row-by-row detecting "is this an item header row or a transaction row" rather than assuming a fixed column mapping per row.
- PDF text extraction (`pdf.js` or similar) for invoice/order-confirmation parsing; expect to special-case Kyocera's fixed-width tabular layout (item no / description+spec on two lines / qty / unit / price / % / net price / shipping date).
- Keep parsing logic isolated behind a clear interface per document type so a new vendor's format can be added later without touching the matching/exceptions logic.

## 11. Sample data reference (from files provided)

These shapes were taken directly from the sample files supplied for this project and should drive the parser design and data model field types.

**Price list (`Kyocera_Price_File`, one row per item, ~168 rows):**
```
Item number | Cust Item Name | Text 2 | Price Before Discount | Discount | Current Price | New Price - effective <date> | Increase | Nominal Code
TLC56283 | Carbide Turning Insert | TNMG160412MS PR1535 | 13 | 0.5 | 5.92 | 6.50 | 0.58 | 7700
ISC5508377 | Iscar drilling insert | ICM 107 IC908 | (blank) | (blank) | 65.52 | 65.52 | 0 | 7700
```
Most rows have blank "Price Before Discount"/"Discount" (unchanged items — current = new, increase = 0); only rows with an actual price change carry those two columns populated. Nominal codes observed: 7504, 7700, 7801, 8202 — expect this list to grow as product range expands (per notes, it "starts mostly with tooling").

**Order confirmation (PDF, two-line-per-item layout):**
```
Item No.    Description                  Qty  Unit  Price each  %      Net price  Shipping Date
ISC5592941  Iscar turning insert         14   PCS   8.05        30.00  78.89      13/07/2026
            CCMT 060202 PF IC907
```
Header block also carries: Order No., Your Reference (date range, e.g. `WSF VEND 09.07-12.07`), Date of Order Confirmation, Customer No., Currency, and a totals block (Net Price, Delivery, Insurance, Battery Fee, Total Net, Total VAT 20%, Total amount due).

**Invoice (PDF) — confirmed against a real sample, matches the order confirmation almost exactly:**
```
Item No.    Description                  Qty  Unit  Price each  %      Net price
ISC5592941  Iscar turning insert         14   PCS   8.05        30.00  78.89
            CCMT 060202 PF IC907
```
Same item numbers, quantities, unit prices, discount %, and net prices as the order confirmation for the same order (confirms the assumption that one parser can serve both document types). Differences from the order confirmation layout: no `Shipping Date` column; header adds `Invoice Number`, `Invoice Date`, `Due Date`, and `Delivery Note No.` (the order number plus a suffix, e.g. `5139526-0` for order `5139526` — the field that ties an invoice back to its order confirmation); footer adds bank details and "Any price discrepancy should be reported within 21 days". Totals block layout: Net Price, Delivery/Insurance, Total Net, Total VAT 20%, Total amount due.

**Vend report (`.xls`, hierarchical, not flat):**
```
row: item header  -> spec code | description | supplier item no (x2) | trans. count | quantity (neg) | amount (neg)
row(s): transaction detail -> location code | date (excel serial) | time (fraction) | type ('I') | qty (neg) | pack qty | unit price | badge no | amount (neg)
```
Example item header: `CCMT 060202 PF IC907 | Iscar turning insert | ISC5592941 | ISC5592941 | 3 | -14 | -78.89`, followed by 2–3 transaction rows whose quantities sum to the header's total. Quantities and amounts are negative in the source (stock leaving the machine); normalize to positive magnitudes for matching/display.

**Consignment addition sheet (`.xlsx`, different document family — referenced for context only, not part of the three-way match):**
```
Total Cons Qty Required | Preferred Cons Min/Max | Requested By | Aspect Item No. | Description 1 | Preferred Vend Description | List Price & Disc. | Item Category
15 | 10&20 | Simon | (blank) | TCMT 110204E-FM T8430 | (blank) | £9.93 less 20% | 2
```
This is a separate vendor-facing form (consignment stock requests, different account structure) rather than a Kyocera reconciliation document. It's included here only as evidence of how irregular/merged-cell vendor spreadsheets can be, reinforcing the need for tolerant parsing rather than rigid fixed-column assumptions — it is **not** a required document type for this app's core workflow.

## 12. Open questions / assumptions to flag back to the user

- Return/credit handling on the vend report is unconfirmed (action item: check with Simon) — built as "flag, don't fail" rather than a full workflow for now.
- Backup/DR strategy for session and price-list data is still being scoped with the vendor/infra side — treat §8's note as a placeholder, not a spec to build against yet.
- Automated extraction from secured PDFs is unproven — budget for the manual-conversion fallback being the common path initially, with automation as a stretch goal once more secured-PDF samples are tested.
