"""Tests for src.reporting.pdf_report – PDF generation."""

from pathlib import Path
from src.reporting.pdf_report import generate_pdf_report


class TestPdfReport:
    def test_generates_pdf_file(self, sample_dataframe, tmp_path):
        path = generate_pdf_report(
            df=sample_dataframe,
            filter_id="99999",
            title="Test Report",
            output_dir=tmp_path,
        )
        assert Path(path).exists()
        assert path.suffix == ".pdf"
        assert path.stat().st_size > 0
