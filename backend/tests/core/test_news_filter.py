import pytest

from finalarr.core.news_filter import evidence_sentence, is_season_news, news_kind

MUSHOKU = ["Mushoku Tensei: Jobless Reincarnation", "Mushoku Tensei"]
SLIME = ["That Time I Got Reincarnated as a Slime", "Tensei Shitara Slime Datta Ken"]


@pytest.mark.parametrize(
    ("headline", "titles"),
    [
        ("„Mushoku Tensei“ Staffel 3 Teil 2 startet 2027 - Hypebeast", MUSHOKU),
        (
            "Mushoku Tensei: Jobless Reincarnation Staffel 3 stellt mit Trailer "
            "neue Cast-Mitglieder vor",
            MUSHOKU,
        ),
        ("‘That Time I Got Reincarnated as a Slime’ Season 4 Episode 23 Release Date, Time", SLIME),
        ("Tensei Shitara Slime Datta Ken 4th Season Part 3 dated for July 2027", SLIME),
        ("Severance renewed for season 3 at Apple TV+", ["Severance"]),
        ("Game of Thrones prequel season 3 delayed to 2027", ["Game of Thrones"]),
        ("»Frieren« Folge 12 verschoben – Pause wegen Produktionsproblemen", ["Frieren"]),
        ("The Bear canceled after four seasons", ["The Bear"]),
        ("Dandadan 3rd Season reveals premiere date in new PV", ["DAN DA DAN"]),
    ],
)
def test_season_and_episode_news_is_kept(headline, titles):
    assert is_season_news(headline, titles)


@pytest.mark.parametrize(
    ("headline", "titles"),
    [
        ("Neue Figur von Roxy Migurdia aus »Mushoku Tensei« angekündigt - Anime2You", MUSHOKU),
        ("Neue »Mushoku Tensei«-Modekollektion von COSPA vorgestellt - Anime2You", MUSHOKU),
        ("GARRACK stellt neue Uhrenkollektion zu »Mushoku Tensei« vor", MUSHOKU),
        (
            "Meine Wiedergeburt als Schleim in einer anderen Welt, der Film: Tränen des Meeres",
            SLIME,
        ),
        (
            "Band 32 des Mangas „That Time I Got Reincarnated as a Slime“ erscheint am 9. Juli",
            SLIME,
        ),
        ("That Time I Got Reincarnated as a Slime: Complete Watch Order (2026 Updated)", SLIME),
        ("Chained Soldier Manga Resumes on December 12", ["Chained Soldier"]),
        ("Spy x Family movie trailer revealed", ["SPY x FAMILY"]),
        ("Mushoku Tensei season 3 Nendoroid figure opens for preorder", MUSHOKU),
        ("Slime season 4 collab café opens in Tokyo", SLIME),
        ("Mushoku Tensei Blu-ray box for season 2 announced", MUSHOKU),
        ("Mushoku Tensei light novel volume 27 release date", MUSHOKU),
        ("Interview with the director of Mushoku Tensei", MUSHOKU),
        ("10 Anime to Watch If You Can't Wait for Solo Leveling Season 3", SLIME),
        ("7 Masterpiece Isekai Anime Like Mushoku Tensei season 2, But Better", MUSHOKU),
        ("'Severance' season 2 review: What it means to be you", ["Severance"]),
        ("Severance season 2 recap before season 3", ["Severance"]),
        ("That Time I Got Reincarnated as a Slime Season 4 Opening Song Music Video", SLIME),
        ("Crunchyroll kündigt die deutschen Synchros für Sommer 2026 an, Staffel 2", MUSHOKU),
    ],
)
def test_merchandise_and_other_news_is_dropped(headline, titles):
    assert not is_season_news(headline, titles)


def test_the_series_must_be_named_in_the_headline():
    assert not is_season_news("Solo Leveling Season 3 premieres in January", SLIME)
    assert is_season_news("Dritte »Mushoku Tensei«-Staffel erhält Fortsetzung", MUSHOKU)
    assert is_season_news(
        "Slime season 4 part 3 dated", ["That Time I Got Reincarnated as a Slime", "Slime"]
    )


@pytest.mark.parametrize(
    ("headline", "kind"),
    [
        ("»Re:ZERO« erhält fünfte Staffel + Visual", "renewal"),
        ("Severance renewed for season 3", "renewal"),
        ("Re:ZERO Season 5 Anime Announced", "announcement"),
        ("Mushoku Tensei: Staffel 3 angekündigt", "announcement"),
        ("Re:ZERO season 4 cancelled", "cancellation"),
        ("Re:ZERO: Staffel 4 wird abgesetzt", "cancellation"),
        ("Re:ZERO episode 7 delayed due to production issues", "delay"),
        ("Re:ZERO: Folge 7 verschoben", "delay"),
        ("Re:ZERO Season 4 premieres April 8", "date"),
        ("Re:ZERO: Staffel 4 startet im April", "date"),
        ("New Re:ZERO season 4 trailer", "trailer"),
        ("Re:ZERO episode 5 discussion", "other"),
    ],
)
def test_news_kind(headline, kind):
    assert news_kind(headline) == kind


def test_strong_news_survives_merchandise_words():
    titles = ["Mushoku Tensei"]
    assert is_season_news("Mushoku Tensei season 3 announced alongside new figures", titles)
    assert not is_season_news("Mushoku Tensei season 3 figure revealed", titles)


@pytest.mark.parametrize(
    ("summary", "evidence"),
    [
        (
            "<p>Gute Nachrichten! Die Serie erhält eine <b>fünfte Staffel</b>. Mehr folgt.</p>",
            "Die Serie erhält eine fünfte Staffel.",
        ),
        ("Nothing relevant here at all.", None),
        ("", None),
    ],
)
def test_evidence_sentence(summary, evidence):
    assert evidence_sentence(summary) == evidence


@pytest.mark.parametrize(
    "headline",
    [
        "»DAN DA DAN« wirbt mit Formel-1-Showcar für dritte Staffel",
        "Zweite »DAN DA DAN«-Staffel erhält Steelcase-Edition von AniMoon",
    ],
)
def test_promotion_and_editions_are_dropped(headline):
    assert not is_season_news(headline, ["DAN DA DAN"])
