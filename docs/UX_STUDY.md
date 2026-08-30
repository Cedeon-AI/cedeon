# UX Study — The Ceded Reinsurance Desk

What the person collecting reinsurance recoveries actually does all day, and how
Cedeon's screens should be arranged around that job instead of around its database.

- **Prepared as:** design lead + user, 2026-08-30
- **In scope:** information architecture, in-app flow, wording
- **Not in scope:** the domain model (`PRODUCT.md §1a` stands — no generalised
  financial-exception type, no reshaping of the recovery object)

---

## 1. The gap

Cedeon's navigation today lists eight destinations: Dashboard, Documents, Programs,
Treaty library, Loss imports, Loss events, Recovery candidates, Activity. **Seven of
them are tables in the database.**

The analyst who would use Cedeon does not think in any of them. They think: *a large
loss happened — which of our treaties respond, for how much, from which reinsurers,
and what do we have to do to collect before a deadline passes.* Every rough edge in
this document traces back to that one gap between the schema and the job.

The fix is not a reskin — the visual layer is already good. It is rearranging the same
capabilities around the shape of the work.

---

## 2. Who is at the desk

Four people touch a recovery. Cedeon is built for the first, and should stay that way.

- **Ceded reinsurance analyst / manager** — *the primary user.* Owns the treaty
  register and every recovery. Lives in Excel and a shared drive of contract PDFs, with
  a reinsurance-administration system of record behind them (SICS, Sapiens, Xuber).
  Judged on: recoveries identified and collected, notices filed inside the deadline, a
  claim file the broker cannot push back on.
- **Reinsurance accountant** — books the recoverable as an asset, then reconciles the
  expected figure against what is billed against cash actually collected. Needs one
  number to book now, and a collection ledger later.
- **Head of ceded reinsurance** — wants the portfolio: total outstanding recoverable,
  largest single exposure, what is aged, what is disputed, this quarter's catastrophe
  recoveries.
- **Catastrophe / large-loss manager** — upstream. Declares the event, owns the moving
  gross-loss number, hands it over. Touches Cedeon only as a source of loss data.

---

## 3. The actual workflow

It has two rhythms, running on different clocks.

**Setup — annual, once per treaty.** Reinsurance is placed at renewal (1 January,
1 July) through a broker. The signed structure is known at once; the *contract wording
arrives weeks to months later.* When it does, someone reads it and confirms the terms
match what was placed — attachment, limit, reinstatements, the occurrence definition,
exclusions. That confirmed wording goes into the treaty register. This is precisely
what Cedeon's validation workspace is for.

**Operate — event-driven, on the catastrophe's clock.**

```
SETUP   -- annual, per treaty ------------------------------------------
  renewal -> broker places -> wording arrives (weeks-months)
          -> confirm terms match the placement -> treaty register

OPERATE -- per event, on the catastrophe's clock ----------------------
  event declared (name . dates . peril . hours clause)
     -> gross loss accumulates over weeks
     -> identify which layers respond
     -> compute:  loss xs attachment, capped at limit
                  then reinstatement, aggregate deductible
     -> allocate to each reinsurer by signed line
     -> NOTIFY reinsurers + broker  <-- contractual deadline
     -> book the recoverable (an asset)
     -> notified -> acknowledged -> agreed -> billed -> collected -> aged
     -> re-run steps whenever the gross loss develops
```

Two things about that lower track matter for the design. The **notice** step is
time-boxed by the contract, and missing it is how recoveries get contested. And the
work does not end at a settlement — it ends at *cash in the bank*, often a year or more
later, after chasing overdue balances across a dozen reinsurers.

---

## 4. What Cedeon already gets right

None of the redesign below touches any of this. It is the reason the product is worth
using.

- The **validation workspace** — treaty page beside the extracted term, confirm / edit
  / reject. The right tool for the confirm-the-wording job. Keep it exactly.
- **Provenance on every term** and the **FACT / CALCULATION / AI INTERPRETATION /
  HUMAN DECISION** language. This is the analyst's defence when a reinsurer pushes back
  — Cedeon's best idea.
- **Deterministic calculation** with a visible trace, re-run when inputs change.
- The **notice-obligation findings** from the investigator. Surfacing a deadline before
  it is missed can justify the whole product.
- The **recovery packet** as an immutable, classified artifact, and the **audit trail**
  and **no-send** rule behind it.

---

## 5. Where it works against the desk

1. **The navigation is a schema browser.** Eight destinations, seven of them database
   tables. The analyst has to learn Cedeon's internal model before they can do their
   job inside it.
2. **Setup is a chain of hidden prerequisites.** To get one treaty in: upload a PDF,
   wait for parsing, add a cedent, add a program, create a treaty pointing at the
   document, wait for extraction, open the workspace, confirm terms, validate. Nine
   steps across five screens, and nothing states the order — you discover each
   dependency by hitting a wall ("No validated treaties yet", "Upload & parse a treaty
   PDF first").
3. **"Loss import" and "loss event" are two hops the user never takes.** They have *the
   Hurricane Béatrice claims file* and they want *the Hurricane Béatrice recovery.*
   Cedeon makes them create and name an intermediate "loss event" object and navigate
   to it as a destination in its own right.
4. **The words are the database's, not the desk's.** *Recovery candidate. Underlying
   losses. Term candidates. Loss import row.* The analyst says *recovery*, *claims*,
   *the wording*, *the proposed terms*.
5. **There is no worklist.** The dashboard is four empty stat tiles and six generic
   links. Nothing answers *what needs me today* — which terms wait to be validated,
   which recoveries need review, which packets are mid-approval, which notices are
   unsent and how close to the deadline.
6. **The pipeline is invisible.** Nowhere shows a recovery's position at a glance:
   *Béatrice — wording confirmed, losses in, calculation done, investigation done,
   packet in review, notice not started.* You reconstruct it by visiting four screens.
7. **The story ends at "notice approved."** The accountant's and the head of desk's
   entire job — booked, billed, collected, aged — has no home. A recovery's terminal
   state in Cedeon is a drafted notice; a recovery's terminal state at the desk is cash
   received.
8. **The judgement calls are buried.** The occurrence definition, the hours clause,
   whether a reinstatement premium is due, whether this peril is in scope — these are
   the decisions that win or lose a recovery, and they are the analyst's to make.
   Today they are entries in a term list, not decisions the workflow asks for.
9. **One recovery equals one treaty × one layer.** A real programme is three to five
   stacked layers; a single event hits several at once and the analyst works the stack
   together. This is a domain-model limit — noted for the roadmap, not for this
   redesign.

---

## 6. The redesign

Information architecture, flow, and wording only. The API barely moves — the wizards
call endpoints that already exist.

### Information architecture — four areas, named for the work

| Today | Proposed | What it is |
| --- | --- | --- |
| Dashboard | **Home** | A worklist — what needs you — with the portfolio at a glance above it. |
| Documents · Programs · Treaty library | **Reinsurance programme** | The treaty register. A document attaches *inside* a treaty; it is not a place you go. |
| Loss imports · Loss events | *folded into a recovery* | Claims data is a step in *starting a recovery*, not a destination. |
| Recovery candidates | **Recoveries** | One row per event × layer, each showing its stage in the pipeline. |
| Activity | **Audit log** | Unchanged. An oversight tool, correctly separate. |

### Home — the worklist

```
+- HOME --------------------------------------------------------------+
|                                                                    |
|  Needs you                                              6 open      |
|  +--------------------------------------------------------------+   |
|  | ^  Notice . Beatrice -> Reinsurer Alpha       unsent . 2 days |  |
|  | *  Recovery . Windstorm Cara                  calculation review|
|  | *  4 proposed terms . 2027 Casualty XOL           to validate  |  |
|  | *  Packet . Beatrice v3                       approval pending  |  |
|  +--------------------------------------------------------------+   |
|                                                                    |
|  Open recoverable   Largest open     This quarter    Avg to notice  |
|  $14,310,000        $8,700,000       3 recoveries     1.8 days      |
|                                                                    |
|  Recent events                       Programme health              |
|  Beatrice   $58.7M   1 recovery      2 treaties need validation     |
|  Cara       $31.2M   in progress     1 treaty expires in 40 days    |
+--------------------------------------------------------------------+
```

"Needs you" is one queue, mixing every kind of pending action, sorted by urgency — a
notice near its deadline outranks a packet awaiting a signature. The four figures are
the ones the head of desk asks about. This is finding 5 and finding 6, answered on the
first screen.

### Set up a treaty — a wizard, not five screens

```
  (1)---------(2)---------(3)---------(4)---------(5)
  Upload      Extract     Validate    Confirm     Activate
  wording    (progress)   terms       structure

  -- on (3) Validate terms ---------------------------------------
  +---------------------------+-------------------------------+
  | ARTICLE 4 - LIMIT & RETEN.|  CALCULATION   Attachment      |
  | ...liable for the amount  |  USD 50,000,000               |
  | which exceeds a retention |  p.3 . Article 4 . conf. 0.92  |
  | of USD 50,000,000 ... not |                               |
  | exceed USD 20,000,000     |  [ Confirm ]  [ Edit ]        |
  +---------------------------+-------------------------------+
     the existing two-pane workspace, unchanged -- now step (3)
```

The cedent and programme are fields in step 4, created inline, not separate errands.
The wizard saves and resumes; the register shows each treaty parked at its step. This
is finding 2.

### Start a recovery — a wizard

```
  (1)--------------(2)--------------(3)--------------(4)
  Event            Claims           Responding        Calculate
                                    layer

  -- (1) Event ------------------------------------------------
     Name          Hurricane Beatrice
     Date range    14-17 Sep 2027
     Peril         Named windstorm
     Hours clause  168 hours        <-- the judgement call, asked up front

  -- (2) Claims -----------------------------------------------
     drop the claims CSV -> map columns -> commit
     (the loss-import screen, inline -- no separate destination)
```

Step 1 is where finding 8 gets fixed: the occurrence definition and the hours clause
are the first thing the workflow asks for, because they are the first thing the analyst
decides. Step 2 absorbs "loss import" and "loss event" (finding 3). You end step 4
inside the workspace.

### The recovery workspace — one page, one rail

```
+- RECOVERY . Hurricane Beatrice x Property Cat XOL 2027 ------------+
|                                            status   Needs review   |
|                                                                    |
|  o Loss basis      |  CALCULATION                                   |
|  * Calculation  <  |  +------------------------------------------+  |
|  o Investigation   |  | CALCULATION   Layer recovery              |  |
|  o Packet          |  |               $8,700,000.00              |  |
|  o Notice          |  | engine v1.0.0                            |  |
|  o Collection      |  | 58,700,000 - 50,000,000  =  8,700,000    |  |
|                    |  | min(8,700,000, 20,000,000)               |  |
|                    |  +------------------------------------------+  |
|                    |  | Alpha   50%    $4,350,000.00             |  |
|                    |  | Beta    30%    $2,610,000.00             |  |
|                    |  | Gamma   20%    $1,740,000.00             |  |
|                    |  +------------------------------------------+  |
|                    |  [ Confirm ]   [ Recalculate ]   [ Reject ]    |
+--------------------------------------------------------------------+
```

One URL for the whole recovery. The rail is the pipeline made visible (finding 6); each
stage opens in place, and each carries its trust class — the loss basis is *fact*, the
number is *calculation*, the investigator's read is *AI interpretation*, your sign-off
is *human decision*. **Collection** is greyed until it is built (phase C) — but it is on
the rail from day one so the shape of the job is honest.

### Wording

| System term | Desk term |
| --- | --- |
| Recovery candidate | **Recovery** (status: draft / needs review / confirmed) |
| Underlying losses | **Claims** |
| Term candidate | **Proposed term** |
| Loss import | **Import claims** (an action) |
| Loss event | **Event** (created inside a recovery) |
| Treaty library | **Reinsurance programme** |

---

## 7. What stays fixed

The domain model does not move. No generalised financial-exception type, no reshaping
of the recovery object — `PRODUCT.md §1a` stands. The trust-class language,
deterministic calculation, provenance, the packet, the audit trail and the no-send
rule are all unchanged. This is information architecture, flow and wording.

---

## 8. Doing it in order

- **A · Reframe** — *UI only, days not weeks. Recommended first, on its own.* The
  four-area navigation, the Home worklist, the two wizards wrapped around the endpoints
  that already exist, Documents folded into the treaty, the rename. This is most of the
  felt improvement, and it is mostly moving and relabelling what is already built.
- **B · The recovery workspace** — *UI, one to two weeks.* The single-page workspace
  and its progress rail; claims import inline.
- **C · Collection tracking** — *a new phase, small model addition, its own decision
  record.* The recoverable as a first-class object moving notified → agreed → billed →
  collected → aged. This is what turns Cedeon from a calculator into the desk's system.
- **D · Programme depth** — *model work, roadmap.* Multi-layer programmes and
  reinstatement premiums (finding 9).

**Recommendation:** ship A on its own and put it in front of a real ceded-reinsurance
analyst before committing to B. A is cheap, reversible, and the fastest way to learn
whether the mental model in this document is right.

---

## 9. Test data — ready now

`packages/fixtures/` holds the end-to-end data:

| File | Use |
| --- | --- |
| `treaty-2027-property-cat-xol.pdf` | Minimal wording extraction is tuned against — a guaranteed-clean run |
| `reinsurance-contract-2027.pdf` | Fuller five-page contract (occurrence definition, 168-hour clause, reinstatement, exclusions, currency, schedule of reinsurers) — realistic demo, same key terms |
| `hurricane-demo-2027-claims.csv` | 10 hurricane claims, USD 58,700,000.00 gross, non-canonical headers so you exercise column mapping |
| `messy-claims-example.csv` | 7 rows that trip every validation rule |

Golden path: `$20M xs $50M`, reinsurers `50 / 30 / 20`, a `$58.7M` event → an
`$8,700,000.00` recovery (`4.35M / 2.61M / 1.74M`). Step-by-step click-through is in
`packages/fixtures/README.md`. Regenerate with
`cd apps/api && uv run python ../../packages/fixtures/generate_fixtures.py`.
