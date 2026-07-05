from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.statement_parser import parse_pdf_text, parse_statement_file


def test_pdf_parser_supports_common_bank_statement_lines():
    text = """
    Statement Period 01 Jun 2026 to 30 Jun 2026
    12 Jun 2026 AMAZON SELLER SERVICES 5,000.00 Dr
    13-Jun-2026 SWIGGY BLR 1,200.00 DR Cashback 12
    14/06/2026 PAYMENT RECEIVED 10000.00 Cr
    15/06/2026 MMT INDIA ONLINE Rs. 12,500.00 Dr
    """
    rows = parse_pdf_text(text)
    merchants = [row["merchant_raw"] for row in rows]
    assert "AMAZON SELLER SERVICES" in merchants
    assert "SWIGGY BLR" in merchants
    assert "MMT INDIA ONLINE" in merchants
    assert all("PAYMENT" not in merchant for merchant in merchants)
    swiggy = next(row for row in rows if row["merchant_raw"] == "SWIGGY BLR")
    assert str(swiggy["amount_inr"]) == "1200.00"
    assert str(swiggy["actual_value_inr"]) == "12"


def test_sample_text_pdf_parses_transactions():
    sample_pdf = ROOT / "data" / "sample_statement_text_pdf.pdf"
    rows = parse_statement_file(str(sample_pdf), sample_pdf.read_bytes())
    assert len(rows) >= 4
    assert any(row["merchant_raw"].lower().startswith("amazon") for row in rows)
