from price_gap import gap_pct


def test_ask_below_reference_is_positive_gap():
    assert round(gap_pct(100.0, 98.0), 6) == 2.0


def test_ask_above_reference_is_negative_gap():
    assert gap_pct(100.0, 101.0) < 0
