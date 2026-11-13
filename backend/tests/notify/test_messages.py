from finalarr.notify.messages import episode_ranges, render

PAYLOAD = {
    "title": "Slime <3>",
    "season": 3,
    "have": 7,
    "expected": 12,
    "sonarr_url": "http://sonarr:8989/series/slime",
}


def test_ranges():
    assert episode_ranges([1, 2, 3, 5, 7, 8]) == "E01–E03, E05, E07–E08"
    assert episode_ranges([]) == ""


def test_available_de_with_escaped_title_and_links():
    text = render(
        "episodes_available",
        {**PAYLOAD, "episodes": [5, 6, 7]},
        "de",
        "https://finalarr.lan/series/4",
    )
    assert "<b>Slime &lt;3&gt;</b> S03 E05–E07 verfügbar (7/12)" in text
    assert '<a href="https://finalarr.lan/series/4">Finalarr</a>' in text
    assert '<a href="http://sonarr:8989/series/slime">Sonarr</a>' in text


def test_every_type_in_both_languages():
    cases = {
        "episodes_available": ({"episodes": [1]}, "verfügbar", "available"),
        "finale_available": ({"finale_number": 12}, "Finale", "Finale"),
        "season_complete": ({}, "komplett", "complete"),
        "part_complete": ({"part": 1}, "Teil 1 komplett", "part 1 complete"),
        "season_announced": ({"first_air": "2027-04-05"}, "Start 05.04.2027", "starts 05/04/2027"),
    }
    for kind, (extra, de, en) in cases.items():
        assert de in render(kind, {**PAYLOAD, **extra}, "de", None), kind
        assert en in render(kind, {**PAYLOAD, **extra}, "en", None), kind


def test_parts_mode_names_the_part():
    text = render(
        "part_complete",
        {**PAYLOAD, "part": 2, "part_title": "Mushoku II Part 2", "parts_mode": "parts"},
        "de",
        None,
    )
    assert "<b>Mushoku II Part 2</b> komplett" in text


def test_announcement_without_date_and_links():
    text = render("season_announced", {"title": "X", "season": 2, "expected": None}, "de", None)
    assert text.startswith("📅 <b>X</b>: Staffel 2 angekündigt")
    assert "href" not in text


def test_unknown_language_falls_back_to_german():
    assert "verfügbar" in render("episodes_available", {**PAYLOAD, "episodes": [1]}, "fr", None)


def test_sequel_announced_with_year_only_and_full_date():
    payload = {
        "title": "Mushoku Tensei",
        "sequel_title": "Mushoku Tensei III Part 2",
        "first_air": "2027-01-01",
    }
    assert (
        "Mushoku Tensei</b>: Fortsetzung angekündigt – Mushoku Tensei III Part 2 (Start 2027)"
        in render("sequel_announced", payload, "de", None)
    )
    assert "sequel announced – Mushoku Tensei III Part 2 (starts 2027)" in render(
        "sequel_announced", payload, "en", None
    )
    dated = render("sequel_announced", {**payload, "first_air": "2027-07-04"}, "de", None)
    assert "(Start 04.07.2027)" in dated


def test_news_mention_links_the_article():
    payload = {
        "title": "Mushoku Tensei",
        "headline": "Season 3 Part 2 <premiere>",
        "link": "https://news.example/a",
    }
    text = render("news_mention", payload, "de", "https://f.lan/series/1")
    assert "<b>Mushoku Tensei</b> in den News: Season 3 Part 2 &lt;premiere&gt;" in text
    assert (
        '<a href="https://news.example/a">Artikel</a> · <a href="https://f.lan/series/1">Finalarr</a>'
        in text
    )
    assert "in the news" in render("news_mention", payload, "en", None)
