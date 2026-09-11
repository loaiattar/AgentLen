from agentlen.domain.model.import_run import ImportReport


def test_success_rate_is_unknown_when_no_record_was_read() -> None:
    report = ImportReport(
        records_read=0,
        records_imported=0,
        records_duplicate=0,
        records_rejected=0,
    )

    assert report.success_rate is None


def test_success_rate_is_zero_when_records_were_read_but_none_imported() -> None:
    report = ImportReport(
        records_read=2,
        records_imported=0,
        records_duplicate=0,
        records_rejected=2,
    )

    assert report.success_rate == 0.0
