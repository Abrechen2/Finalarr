from finalarr.core.fingerprint import fingerprint


def test_same_inputs_same_fingerprint():
    assert fingerprint("season_complete", 1, 42, 3, "12") == fingerprint(
        "season_complete", 1, 42, 3, "12"
    )


def test_every_component_changes_the_fingerprint():
    base = ("season_complete", 1, 42, 3, "12")
    variants = [
        ("finale_available", 1, 42, 3, "12"),
        ("season_complete", 2, 42, 3, "12"),
        ("season_complete", 1, 43, 3, "12"),
        ("season_complete", 1, 42, 4, "12"),
        ("season_complete", 1, 42, 3, "24"),
    ]
    assert len({fingerprint(*v) for v in [base, *variants]}) == len(variants) + 1
