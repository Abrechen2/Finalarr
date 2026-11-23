"""Sets up a fresh Jellyfin: wizard, a TV library, a second user, an API key, plays."""

import json
import sys
import time

import requests

U = "http://127.0.0.1:18096"
AUTH = 'MediaBrowser Client="finalarr-test", Device="ci", DeviceId="finalarr-ci", Version="1.0"'
h = {"Authorization": AUTH, "Content-Type": "application/json"}


def ok(r):
    if r.status_code >= 400:
        sys.exit(f"{r.request.method} {r.url} -> {r.status_code} {r.text[:300]}")
    return r


for _ in range(30):  # /System/Info/Public answers before the rest is ready
    try:
        if requests.get(f"{U}/Startup/User", headers=h, timeout=5).ok:
            break
    except requests.ConnectionError:
        pass
    time.sleep(2)
ok(
    requests.post(
        f"{U}/Startup/Configuration",
        headers=h,
        json={"UICulture": "en-US", "MetadataCountryCode": "DE", "PreferredMetadataLanguage": "en"},
    )
)
ok(
    requests.post(
        f"{U}/Startup/User", headers=h, json={"Name": "dennis", "Password": "test-pass-123"}
    )
)
ok(requests.post(f"{U}/Startup/Complete", headers=h))
login = ok(
    requests.post(
        f"{U}/Users/AuthenticateByName",
        headers=h,
        json={"Username": "dennis", "Pw": "test-pass-123"},
    )
).json()
th = {
    "Authorization": AUTH + f', Token="{login["AccessToken"]}"',
    "Content-Type": "application/json",
}
ok(
    requests.post(
        f"{U}/Library/VirtualFolders",
        headers=th,
        params={
            "name": "Shows",
            "collectionType": "tvshows",
            "paths": "/media/shows",
            "refreshLibrary": "true",
        },
        json={"LibraryOptions": {}},
    )
)
ok(requests.post(f"{U}/Library/Refresh", headers=th))
anna = ok(
    requests.post(f"{U}/Users/New", headers=th, json={"Name": "anna", "Password": "x"})
).json()
ok(requests.post(f"{U}/Auth/Keys", headers=th, params={"app": "Finalarr"}))
key = ok(requests.get(f"{U}/Auth/Keys", headers=th)).json()["Items"][0]["AccessToken"]
for _ in range(60):
    items = ok(
        requests.get(
            f"{U}/Items",
            headers=th,
            params={"Recursive": "true", "IncludeItemTypes": "Episode", "Fields": "ProviderIds"},
        )
    ).json()
    if items["TotalRecordCount"] >= 22:
        break
    time.sleep(3)
eps = items["Items"]
print("episodes", items["TotalRecordCount"])


def played(user, pick):
    for e in eps:
        if pick(e):
            r = requests.post(f"{U}/UserPlayedItems/{e['Id']}", headers=th, params={"userId": user})
            if r.status_code == 404:
                r = requests.post(f"{U}/Users/{user}/PlayedItems/{e['Id']}", headers=th)
            ok(r)


me = login["User"]["Id"]
played(
    me,
    lambda e: e.get("SeriesName", "").startswith("Severance") and e.get("ParentIndexNumber") == 1,
)
played(
    me,
    lambda e: e.get("SeriesName", "").startswith("Frieren") and e.get("IndexNumber") in (1, 2, 3),
)
played(me, lambda e: e.get("SeriesName", "").startswith("Unknown"))
played(
    anna["Id"],
    lambda e: (
        e.get("SeriesName", "").startswith("Severance")
        and e.get("ParentIndexNumber") == 2
        and e.get("IndexNumber") == 1
    ),
)
series = ok(
    requests.get(
        f"{U}/Items",
        headers=th,
        params={"Recursive": "true", "IncludeItemTypes": "Series", "Fields": "ProviderIds"},
    )
).json()["Items"]
print("series", [(s["Name"], s.get("ProviderIds")) for s in series])
open(sys.argv[1], "w").write(json.dumps({"key": key, "me": me, "anna": anna["Id"]}))
