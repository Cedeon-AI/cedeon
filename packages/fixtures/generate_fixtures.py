"""Regenerate the demo fixtures in this directory.

Run from the repo root:  cd apps/api && uv run python ../../packages/fixtures/generate_fixtures.py

Produces:
  treaty-2027-property-cat-xol.pdf   the minimal, extraction-tuned wording (matches the tests)
  reinsurance-contract-2027.pdf      a fuller, realistic contract for demoing the product
  hurricane-demo-2027-claims.csv     10 clean hurricane claims summing to USD 58,700,000.00
  messy-claims-example.csv           a small file that exercises every validation rule

The golden numbers: $20,000,000 xs $50,000,000, reinsurers 50/30/20, a $58.7M
event -> an $8,700,000.00 layer recovery (4.35M / 2.61M / 1.74M).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

HERE = Path(__file__).parent


def _write_pdf(path: Path, pages: list[list[tuple[str, float]]]) -> None:
    doc = pymupdf.open()
    for blocks in pages:
        page = doc.new_page(width=595, height=842)
        y = 64.0
        for text, size in blocks:
            page.insert_textbox(pymupdf.Rect(64, y, 531, 800), text, fontsize=size, fontname="helv")
            y += (1 + len(text) // 92) * (size + 4) + 16
    path.write_bytes(doc.tobytes())
    doc.close()


REALISTIC_CONTRACT: list[list[tuple[str, float]]] = [
    [
        ("PROPERTY CATASTROPHE EXCESS OF LOSS REINSURANCE CONTRACT", 17.0),
        ("Contract Reference: PCX-2027-0142", 10.0),
        (
            "between DEMO SPECIALTY INSURANCE CO., Miami, Florida (hereinafter the "
            '"Company") and the Subscribing Reinsurers identified in the Schedule of '
            'Reinsurers (hereinafter the "Reinsurer").',
            10.0,
        ),
        ("Programme: 2027 Property Catastrophe Programme", 10.0),
        ("Effective: 1 January 2027   Expiry: 31 December 2027, both days inclusive, "
         "Losses Occurring During.", 10.0),
    ],
    [
        ("ARTICLE 1 - BUSINESS COVERED", 14.0),
        (
            "This Contract is to indemnify the Company in respect of the Ultimate Net Loss "
            "which may accrue to the Company under its policies classified by the Company as "
            "Property business, in force at the inception of, or issued or renewed during "
            "the period of this Contract, arising out of loss occurrences commencing during "
            "the term hereof.",
            10.0,
        ),
        ("ARTICLE 2 - TERRITORIAL SCOPE", 14.0),
        (
            "United States of America, its territories and possessions, subject to the "
            "exclusions set out in Article 8.",
            10.0,
        ),
        ("ARTICLE 3 - DEFINITION OF LOSS OCCURRENCE", 14.0),
        (
            "The term 'loss occurrence' shall mean all individual losses arising out of and "
            "directly occasioned by one catastrophe. The duration and extent of any loss "
            "occurrence shall be limited to all individual losses sustained by the Company "
            "occurring during any period of 168 consecutive hours arising out of a named "
            "atmospheric disturbance (hurricane, tropical storm), and 72 consecutive hours "
            "for any other peril. The Company may choose the date and time when any such "
            "period commences.",
            10.0,
        ),
    ],
    [
        ("ARTICLE 4 - LIMIT AND RETENTION", 14.0),
        (
            "The Reinsurer shall be liable for 100% of the amount of Ultimate Net Loss over "
            "and above an initial Ultimate Net Loss to the Company of USD 50,000,000 each "
            "and every loss occurrence. The liability of the Reinsurer shall not exceed USD "
            "20,000,000 each and every loss occurrence, nor USD 40,000,000 in the aggregate "
            "for the period of this Contract.",
            10.0,
        ),
        ("ARTICLE 5 - REINSTATEMENT", 14.0),
        (
            "In the event of the whole or any portion of the reinsurance under this Contract "
            "being exhausted by loss, the amount so exhausted shall be automatically "
            "reinstated from the time of the loss occurrence, subject to a maximum of one "
            "(1) reinstatement. The Company shall pay an additional premium calculated at "
            "100% of the pro rata reinstatement premium as to amount reinstated, at 100% "
            "as to time.",
            10.0,
        ),
        ("ARTICLE 6 - ULTIMATE NET LOSS", 14.0),
        (
            "'Ultimate Net Loss' means the sum actually paid by the Company in settlement "
            "of losses or liability after making deductions for all recoveries, all "
            "salvages and all claims upon other reinsurances, whether collected or not, "
            "and shall include the Company's loss adjustment expense.",
            10.0,
        ),
    ],
    [
        ("ARTICLE 7 - NOTICE OF LOSS AND LOSS SETTLEMENTS", 14.0),
        (
            "The Company shall advise the Reinsurer promptly of each loss occurrence which, "
            "in the opinion of the Company, may result in a claim hereunder, and in any "
            "event within 30 days of the Company establishing a case reserve for such loss "
            "occurrence equal to or greater than 50% of the Company's retention. All loss "
            "settlements made by the Company, provided they are within the terms of this "
            "Contract, shall be binding upon the Reinsurer, and the Reinsurer shall pay "
            "amounts due within 15 business days of receipt of proof of loss.",
            10.0,
        ),
        ("ARTICLE 8 - EXCLUSIONS", 14.0),
        (
            "This Contract does not cover: (a) any loss or liability arising from war, "
            "invasion or civil war; (b) any loss arising from nuclear incident; (c) any "
            "liability of the Company arising from Financial Guarantee or Credit business; "
            "(d) flood as an original peril where written as a stand-alone policy; (e) any "
            "loss occurrence arising outside the Territorial Scope.",
            10.0,
        ),
        ("ARTICLE 9 - CURRENCY", 14.0),
        (
            "All amounts under this Contract are expressed and payable in United States "
            "Dollars (USD).",
            10.0,
        ),
    ],
    [
        ("SCHEDULE OF REINSURERS AND PARTICIPATIONS", 14.0),
        (
            "The following Reinsurers subscribe to this Contract in the proportions set "
            "against their names, severally and not jointly:",
            10.0,
        ),
        ("Reinsurer Alpha Re S.A.           50.0%", 10.0),
        ("Reinsurer Beta Reinsurance Ltd.   30.0%", 10.0),
        ("Reinsurer Gamma Insurance Co.     20.0%", 10.0),
        ("Total placed                     100.0%", 10.0),
        ("ARTICLE 10 - PREMIUM", 14.0),
        (
            "The Company shall pay to the Reinsurer an annual deposit premium of USD "
            "3,600,000, payable in four equal quarterly instalments, subject to adjustment "
            "at a rate of 2.10% of the Company's Gross Net Earned Premium Income for the "
            "period, with a minimum premium of USD 3,060,000.",
            10.0,
        ),
    ],
]


def main() -> None:
    sys.path.insert(0, "tests")
    from tests.support.losses import golden_loss_csv, messy_loss_csv
    from tests.support.pdfs import build_treaty_pdf

    (HERE / "treaty-2027-property-cat-xol.pdf").write_bytes(build_treaty_pdf())
    _write_pdf(HERE / "reinsurance-contract-2027.pdf", REALISTIC_CONTRACT)
    (HERE / "hurricane-demo-2027-claims.csv").write_bytes(golden_loss_csv())
    (HERE / "messy-claims-example.csv").write_bytes(messy_loss_csv())

    for p in sorted(HERE.glob("*.pdf")) + sorted(HERE.glob("*.csv")):
        print(f"  {p.name:38} {p.stat().st_size:>6} bytes")


if __name__ == "__main__":
    main()
