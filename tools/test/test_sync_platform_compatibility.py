#!/usr/bin/env python3

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError


PROJECT_ROOT = Path(__file__).parents[2]
MODULE_PATH = PROJECT_ROOT / "tools/sync-platform-compatibility.py"
SPEC = importlib.util.spec_from_file_location(
    "sync_platform_compatibility", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sync
SPEC.loader.exec_module(sync)


def loader_results(passed: bool = True) -> dict[str, object]:
    return {
        loader: {
            "passed": passed,
            "periodic_toast_absent": passed,
        }
        for loader in sync.EXPECTED_LOADERS
    }


def release_document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "publication": {
            "id": "v1.6.0",
            "release_version": "1.6.0",
            "build_minecraft_version": "26.2",
            "modrinth_project_id": "vAYtksKy",
            "curseforge_project_id": 644324,
            "artifacts": {
                "fabric": {
                    "filename": (
                        "disable_compliance_notification-v1.6.0+fabric-26.2.jar"
                    ),
                    "sha256": "a" * 64,
                    "modrinth_version_id": "fabric-version-id",
                    "modrinth_sha512": "1" * 128,
                    "curseforge_file_id": 710001,
                    "curseforge_loader": "Fabric",
                },
                "neoforge": {
                    "filename": (
                        "disable_compliance_notification-v1.6.0+neoforge-26.2.jar"
                    ),
                    "sha256": "b" * 64,
                    "modrinth_version_id": "neoforge-version-id",
                    "modrinth_sha512": "2" * 128,
                    "curseforge_file_id": 710002,
                    "curseforge_loader": "NeoForge",
                },
                "forge": {
                    "filename": (
                        "disable_compliance_notification-v1.6.0+forge-26.2.jar"
                    ),
                    "sha256": "c" * 64,
                    "modrinth_version_id": "forge-version-id",
                    "modrinth_sha512": "3" * 128,
                    "curseforge_file_id": 710003,
                    "curseforge_loader": "Forge",
                },
            },
        },
        "runtime_verification": [
            {
                "minecraft_version": "26.3",
                "loaders": loader_results(),
            },
            {
                "minecraft_version": "26.2",
                "loaders": loader_results(),
            },
            {
                "minecraft_version": "27.0",
                "loaders": loader_results(),
            },
        ],
    }


def parsed_release() -> object:
    return sync.parse_release_data(release_document())


def release_document_with_versions(
    versions: list[str],
) -> dict[str, object]:
    document = release_document()
    document["runtime_verification"] = [
        {
            "minecraft_version": version,
            "loaders": loader_results(),
        }
        for version in versions
    ]
    return document


def modrinth_version(
    release: object,
    loader: str,
    game_versions: list[str],
) -> dict[str, object]:
    publication = release.publication
    artifact = publication.artifacts[loader]
    return {
        "id": artifact.modrinth_version_id,
        "project_id": publication.modrinth_project_id,
        "version_number": sync.expected_modrinth_version_number(
            publication, loader
        ),
        "game_versions": game_versions,
        "loaders": [loader],
        "files": [
            {
                "filename": artifact.filename,
                "primary": True,
                "hashes": {
                    "sha512": artifact.modrinth_sha512,
                    "sha256": artifact.sha256,
                },
            }
        ],
    }


class FakeClient:
    def __init__(self, responses: dict[tuple[str, str], list[object]]):
        self.responses = {
            key: list(values) for key, values in responses.items()
        }
        self.calls: list[dict[str, object]] = []

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> object:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "body": body,
            }
        )
        key = (method, url)
        if key not in self.responses or not self.responses[key]:
            raise AssertionError(f"unexpected request: {method} {url}")
        response = self.responses[key].pop(0)
        if isinstance(response, Exception):
            raise response
        return copy.deepcopy(response)


class StatefulModrinthClient:
    def __init__(self, release: object, base_url: str):
        self.release = release
        self.base_url = base_url
        self.game_versions = {
            loader: ["26.2"] for loader in sync.EXPECTED_LOADERS
        }
        self.calls: list[dict[str, object]] = []
        self.loader_by_url = {
            sync.modrinth_version_url(
                base_url,
                release.publication.artifacts[loader].modrinth_version_id,
            ): loader
            for loader in sync.EXPECTED_LOADERS
        }

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> object:
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers or {}),
                "body": body,
            }
        )
        loader = self.loader_by_url.get(url)
        if loader is None:
            raise AssertionError(f"unexpected Modrinth URL: {url}")
        if method == "GET":
            return modrinth_version(
                self.release, loader, list(self.game_versions[loader])
            )
        if method == "PATCH":
            if body is None:
                raise AssertionError("missing Modrinth PATCH body")
            payload = json.loads(body)
            versions = payload["game_versions"]
            if len(versions) != len(set(versions)):
                raise AssertionError("Modrinth PATCH introduced duplicates")
            self.game_versions[loader] = list(versions)
            return None
        raise AssertionError(f"unexpected Modrinth method: {method}")


class StatefulCurseForgeClient:
    def __init__(self, release: object, base_url: str):
        self.release = release
        self.base_url = base_url
        self.calls: list[dict[str, object]] = []
        self.game_version_names: dict[str, list[str]] = {}
        self.available_names = [
            {"name": name}
            for name in (
                "Fabric",
                "NeoForge",
                "Forge",
                "26.2",
                "26.2.1",
                "26.3",
            )
        ]
        self.game_versions_url = sync.join_url(
            base_url, "api/game/versions"
        )
        self.update_url = sync.curseforge_update_url(
            base_url, release.publication.curseforge_project_id
        )
        self.loader_by_file_id = {
            release.publication.artifacts[loader].curseforge_file_id: loader
            for loader in sync.EXPECTED_LOADERS
        }

    def request_json(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        body: bytes | None = None,
    ) -> object:
        call = {
            "method": method,
            "url": url,
            "headers": dict(headers or {}),
            "body": body,
        }
        self.calls.append(call)
        if method == "GET" and url == self.game_versions_url:
            return copy.deepcopy(self.available_names)
        if method != "POST" or url != self.update_url:
            raise AssertionError(f"unexpected CurseForge request: {method} {url}")
        metadata = multipart_json(call)
        file_id = metadata["fileID"]
        loader = self.loader_by_file_id.get(file_id)
        if loader is None:
            raise AssertionError(f"unexpected CurseForge file ID: {file_id}")
        names = metadata["gameVersionNames"]
        if len(names) != len(set(names)):
            raise AssertionError("CurseForge update introduced duplicates")
        self.game_version_names[loader] = list(names)
        return {"id": file_id}


def modrinth_responses(
    release: object,
    initial: dict[str, list[str]],
    final: dict[str, list[str]],
) -> dict[tuple[str, str], list[object]]:
    responses: dict[tuple[str, str], list[object]] = {}
    for loader in sync.EXPECTED_LOADERS:
        artifact = release.publication.artifacts[loader]
        url = sync.modrinth_version_url(
            "https://modrinth.test/v2", artifact.modrinth_version_id
        )
        responses[("GET", url)] = [
            modrinth_version(release, loader, initial[loader]),
            modrinth_version(release, loader, final[loader]),
        ]
        if initial[loader] != final[loader]:
            responses[("PATCH", url)] = [None]
    return responses


def multipart_json(call: dict[str, object]) -> dict[str, object]:
    headers = call["headers"]
    assert isinstance(headers, dict)
    content_type = headers["Content-Type"]
    assert isinstance(content_type, str)
    boundary = content_type.split("boundary=", 1)[1]
    body = call["body"]
    assert isinstance(body, bytes)
    prefix = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="metadata"\r\n'
        "Content-Type: application/json\r\n"
        "\r\n"
    ).encode("ascii")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    if not body.startswith(prefix) or not body.endswith(suffix):
        raise AssertionError("invalid multipart body")
    return json.loads(body[len(prefix) : -len(suffix)])


class PublishedReleaseDataTest(unittest.TestCase):
    def test_parses_immutable_coordinates_and_sorts_verified_versions(self):
        release = parsed_release()

        self.assertEqual("v1.6.0", release.publication.publication_id)
        self.assertEqual("644324", release.publication.curseforge_project_id)
        self.assertEqual(
            ("26.2", "26.3", "27.0"),
            release.verified_minecraft_versions,
        )
        self.assertEqual(
            set(sync.EXPECTED_LOADERS),
            set(release.publication.artifacts),
        )
        self.assertEqual(
            "Fabric",
            release.publication.artifacts["fabric"].curseforge_loader,
        )

    def test_loads_the_stable_schema_from_a_repository_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "published-release.json"
            path.write_text(
                json.dumps(release_document()), encoding="utf-8"
            )

            release = sync.load_release_data(path)

        self.assertEqual("1.6.0", release.publication.release_version)

    def test_rejects_unverified_duplicate_or_out_of_range_records(self):
        invalid_documents = []

        incomplete = release_document()
        del incomplete["runtime_verification"][0]["loaders"]["forge"]
        invalid_documents.append((incomplete, "must cover every loader"))

        failed = release_document()
        failed["runtime_verification"][0]["loaders"]["forge"]["passed"] = False
        invalid_documents.append((failed, "is not verified for forge"))

        duplicate = release_document()
        duplicate["runtime_verification"][2]["minecraft_version"] = "26.3"
        invalid_documents.append((duplicate, "duplicate Minecraft versions"))

        older = release_document()
        older["runtime_verification"][2]["minecraft_version"] = "26.1"
        invalid_documents.append((older, "older than the publication build"))

        missing_build = release_document()
        missing_build["runtime_verification"] = missing_build[
            "runtime_verification"
        ][:1]
        invalid_documents.append(
            (missing_build, "does not include the publication build version")
        )

        for document, message in invalid_documents:
            with self.subTest(message=message):
                with self.assertRaisesRegex(sync.PlatformSyncError, message):
                    sync.parse_release_data(document)

    def test_rejects_mutable_or_ambiguous_artifact_coordinates(self):
        invalid_documents = []

        path_filename = release_document()
        path_filename["publication"]["artifacts"]["fabric"][
            "filename"
        ] = "../release.jar"
        invalid_documents.append((path_filename, "must not contain a path"))

        bad_hash = release_document()
        bad_hash["publication"]["artifacts"]["fabric"]["sha256"] = "unsafe"
        invalid_documents.append((bad_hash, "64 hexadecimal digits"))

        wrong_loader = release_document()
        wrong_loader["publication"]["artifacts"]["neoforge"][
            "curseforge_loader"
        ] = "Forge"
        invalid_documents.append((wrong_loader, "must be NeoForge"))

        duplicate_id = release_document()
        duplicate_id["publication"]["artifacts"]["forge"][
            "modrinth_version_id"
        ] = "fabric-version-id"
        invalid_documents.append((duplicate_id, "version IDs must be unique"))

        for document, message in invalid_documents:
            with self.subTest(message=message):
                with self.assertRaisesRegex(sync.PlatformSyncError, message):
                    sync.parse_release_data(document)


class ModrinthSyncTest(unittest.TestCase):
    def test_merges_verified_versions_and_verifies_every_immutable_version(self):
        release = parsed_release()
        complete = ["26.2", "26.3", "27.0"]
        initial = {
            "fabric": ["26.2"],
            "neoforge": complete,
            "forge": ["26.2", "26.3"],
        }
        final = {loader: complete for loader in sync.EXPECTED_LOADERS}
        client = FakeClient(modrinth_responses(release, initial, final))

        summary = sync.sync_modrinth(
            release,
            "dummy-modrinth-token",
            client,
            base_url="https://modrinth.test/v2/",
        )

        self.assertEqual(sync.SyncSummary("modrinth", 3, 2), summary)
        patches = [
            call for call in client.calls if call["method"] == "PATCH"
        ]
        self.assertEqual(2, len(patches))
        patched_ids = {str(call["url"]).rsplit("/", 1)[1] for call in patches}
        self.assertEqual(
            {"fabric-version-id", "forge-version-id"}, patched_ids
        )
        for call in patches:
            self.assertEqual(
                "dummy-modrinth-token",
                call["headers"]["Authorization"],
            )
            self.assertEqual(
                "application/json", call["headers"]["Content-Type"]
            )
            self.assertEqual(
                {"game_versions": complete},
                json.loads(call["body"]),
            )
        gets = [call for call in client.calls if call["method"] == "GET"]
        self.assertEqual(6, len(gets))

    def test_is_idempotent_when_every_verified_version_is_already_present(self):
        release = parsed_release()
        complete = ["26.2", "26.3", "27.0"]
        versions = {loader: complete for loader in sync.EXPECTED_LOADERS}
        client = FakeClient(modrinth_responses(release, versions, versions))

        summary = sync.sync_modrinth(
            release,
            "dummy-token",
            client,
            base_url="https://modrinth.test/v2",
        )

        self.assertEqual(0, summary.updated)
        self.assertFalse(
            any(call["method"] == "PATCH" for call in client.calls)
        )
        self.assertEqual(
            6,
            sum(call["method"] == "GET" for call in client.calls),
        )

    def test_validates_all_coordinates_before_the_first_patch(self):
        release = parsed_release()
        initial = {
            loader: ["26.2"] for loader in sync.EXPECTED_LOADERS
        }
        complete = ["26.2", "26.3", "27.0"]
        final = {
            loader: complete for loader in sync.EXPECTED_LOADERS
        }
        responses = modrinth_responses(release, initial, final)
        forge = release.publication.artifacts["forge"]
        forge_url = sync.modrinth_version_url(
            "https://modrinth.test/v2", forge.modrinth_version_id
        )
        wrong_project = modrinth_version(
            release, "forge", ["26.2"]
        )
        wrong_project["project_id"] = "different-project"
        responses[("GET", forge_url)][0] = wrong_project
        client = FakeClient(responses)

        with self.assertRaisesRegex(
            sync.PlatformSyncError, "belongs to a different project"
        ):
            sync.sync_modrinth(
                release,
                "dummy-token",
                client,
                base_url="https://modrinth.test/v2",
            )

        self.assertFalse(
            any(call["method"] == "PATCH" for call in client.calls)
        )

    def test_rejects_version_loader_filename_and_hash_mismatches(self):
        release = parsed_release()
        artifact = release.publication.artifacts["fabric"]
        valid = modrinth_version(release, "fabric", ["26.2"])
        mutations = [
            (
                lambda value: value.update({"version_number": "1.6.0"}),
                "unexpected version coordinates",
            ),
            (
                lambda value: value.update({"loaders": ["forge"]}),
                "unexpected loaders",
            ),
            (
                lambda value: value["files"][0].update(
                    {"filename": "different.jar"}
                ),
                "does not contain exactly one",
            ),
            (
                lambda value: value["files"][0]["hashes"].update(
                    {"sha512": "f" * 128}
                ),
                "sha512 mismatch",
            ),
            (
                lambda value: value.update({"game_versions": ["26.3"]}),
                "does not advertise its build",
            ),
        ]

        for mutate, message in mutations:
            value = copy.deepcopy(valid)
            mutate(value)
            with self.subTest(message=message):
                with self.assertRaisesRegex(sync.PlatformSyncError, message):
                    sync.validate_modrinth_version(
                        value, release.publication, artifact
                    )

    def test_post_patch_get_must_confirm_all_verified_versions(self):
        release = parsed_release()
        initial = {
            loader: ["26.2"] for loader in sync.EXPECTED_LOADERS
        }
        final = {
            loader: ["26.2", "26.3", "27.0"]
            for loader in sync.EXPECTED_LOADERS
        }
        final["forge"] = ["26.2", "26.3"]
        client = FakeClient(modrinth_responses(release, initial, final))

        with self.assertRaisesRegex(
            sync.PlatformSyncError,
            "did not retain all verified Minecraft versions",
        ):
            sync.sync_modrinth(
                release,
                "dummy-token",
                client,
                base_url="https://modrinth.test/v2",
            )


class CurseForgeSyncTest(unittest.TestCase):
    def responses(self, release: object) -> dict[tuple[str, str], list[object]]:
        base_url = "https://curseforge.test"
        game_versions = [
            {"id": 1, "name": "Fabric"},
            {"id": 2, "name": "NeoForge"},
            {"id": 3, "name": "Forge"},
            {"id": 4, "name": "26.2"},
            {"id": 5, "name": "26.3"},
            {"id": 6, "name": "27.0"},
        ]
        update_url = sync.curseforge_update_url(
            base_url, release.publication.curseforge_project_id
        )
        return {
            ("GET", sync.join_url(base_url, "api/game/versions")): [
                game_versions
            ],
            ("POST", update_url): [
                {
                    "id": release.publication.artifacts[loader].curseforge_file_id
                }
                for loader in sync.EXPECTED_LOADERS
            ],
        }

    def test_posts_full_loader_and_verified_version_metadata(self):
        release = parsed_release()
        client = FakeClient(self.responses(release))

        summary = sync.sync_curseforge(
            release,
            "dummy-curseforge-token",
            client,
            base_url="https://curseforge.test/",
            boundary_factory=lambda: "UnitTestBoundary",
        )

        self.assertEqual(sync.SyncSummary("curseforge", 3, 3), summary)
        self.assertEqual("GET", client.calls[0]["method"])
        posts = [
            call for call in client.calls if call["method"] == "POST"
        ]
        self.assertEqual(3, len(posts))
        for loader, call in zip(sync.EXPECTED_LOADERS, posts):
            artifact = release.publication.artifacts[loader]
            self.assertEqual(
                "dummy-curseforge-token",
                call["headers"]["X-Api-Token"],
            )
            self.assertEqual(
                {
                    "fileID": artifact.curseforge_file_id,
                    "gameVersionNames": [
                        artifact.curseforge_loader,
                        "26.2",
                        "26.3",
                        "27.0",
                    ],
                },
                multipart_json(call),
            )

    def test_fails_before_posting_when_curseforge_lacks_a_required_name(self):
        release = parsed_release()
        responses = self.responses(release)
        game_versions_url = sync.join_url(
            "https://curseforge.test", "api/game/versions"
        )
        responses[("GET", game_versions_url)][0] = [
            {"name": "Fabric"},
            {"name": "NeoForge"},
            {"name": "Forge"},
            {"name": "26.2"},
            {"name": "26.3"},
        ]
        client = FakeClient(responses)

        with self.assertRaisesRegex(
            sync.PlatformSyncError, "does not recognize.*27.0"
        ):
            sync.sync_curseforge(
                release,
                "dummy-token",
                client,
                base_url="https://curseforge.test",
            )

        self.assertEqual(["GET"], [call["method"] for call in client.calls])

    def test_requires_update_response_to_match_the_immutable_file_id(self):
        release = parsed_release()
        responses = self.responses(release)
        update_url = sync.curseforge_update_url(
            "https://curseforge.test",
            release.publication.curseforge_project_id,
        )
        responses[("POST", update_url)][0] = {"id": 999999}
        client = FakeClient(responses)

        with self.assertRaisesRegex(
            sync.PlatformSyncError, "updated the wrong file"
        ):
            sync.sync_curseforge(
                release,
                "dummy-token",
                client,
                base_url="https://curseforge.test",
                boundary_factory=lambda: "UnitTestBoundary",
            )

    def test_multipart_encoder_rejects_unsafe_boundaries(self):
        with self.assertRaisesRegex(
            sync.PlatformSyncError, "invalid multipart boundary"
        ):
            sync.encode_multipart_metadata(
                {"fileID": 1}, "unsafe\r\nboundary"
            )


class HttpClientTest(unittest.TestCase):
    def test_http_errors_do_not_disclose_request_headers(self):
        secret = "secret-that-must-not-be-printed"

        def failing_opener(request, timeout):
            raise HTTPError(request.full_url, 401, "Unauthorized", {}, None)

        client = sync.JsonHttpClient(timeout=1, opener=failing_opener)
        with self.assertRaises(sync.PlatformSyncError) as caught:
            client.request_json(
                "GET",
                "https://marketplace.test/api",
                headers={"Authorization": secret},
            )

        self.assertNotIn(secret, str(caught.exception))
        self.assertIn("HTTP 401", str(caught.exception))


class SequentialCompatibilitySimulationTest(unittest.TestCase):
    def test_new_verified_versions_accumulate_without_duplicate_metadata(self):
        base_url_modrinth = "https://modrinth.test/v2"
        base_url_curseforge = "https://curseforge.test"
        initial_release = sync.parse_release_data(
            release_document_with_versions(["26.2"])
        )
        modrinth = StatefulModrinthClient(
            initial_release, base_url_modrinth
        )
        curseforge = StatefulCurseForgeClient(
            initial_release, base_url_curseforge
        )

        stage_summaries = []
        for versions in (
            ["26.2"],
            ["26.2", "26.2.1"],
            ["26.2", "26.2.1", "26.3"],
        ):
            release = sync.parse_release_data(
                release_document_with_versions(versions)
            )
            stage_summaries.append(
                (
                    sync.sync_modrinth(
                        release,
                        "dummy-modrinth-token",
                        modrinth,
                        base_url=base_url_modrinth,
                    ),
                    sync.sync_curseforge(
                        release,
                        "dummy-curseforge-token",
                        curseforge,
                        base_url=base_url_curseforge,
                        boundary_factory=lambda: "SimulationBoundary",
                    ),
                )
            )

        expected_minecraft_versions = ["26.2", "26.2.1", "26.3"]
        self.assertEqual(
            [0, 3, 3],
            [summaries[0].updated for summaries in stage_summaries],
        )
        self.assertEqual(
            [3, 3, 3],
            [summaries[1].updated for summaries in stage_summaries],
        )
        for loader in sync.EXPECTED_LOADERS:
            self.assertEqual(
                expected_minecraft_versions,
                modrinth.game_versions[loader],
            )
            self.assertEqual(
                [
                    initial_release.publication.artifacts[
                        loader
                    ].curseforge_loader,
                    *expected_minecraft_versions,
                ],
                curseforge.game_version_names[loader],
            )

        patch_count = sum(
            call["method"] == "PATCH" for call in modrinth.calls
        )
        post_count = sum(
            call["method"] == "POST" for call in curseforge.calls
        )
        final_release = sync.parse_release_data(
            release_document_with_versions(expected_minecraft_versions)
        )
        rerun_modrinth = sync.sync_modrinth(
            final_release,
            "dummy-modrinth-token",
            modrinth,
            base_url=base_url_modrinth,
        )
        rerun_curseforge = sync.sync_curseforge(
            final_release,
            "dummy-curseforge-token",
            curseforge,
            base_url=base_url_curseforge,
            boundary_factory=lambda: "SimulationBoundary",
        )

        self.assertEqual(0, rerun_modrinth.updated)
        self.assertEqual(
            patch_count,
            sum(call["method"] == "PATCH" for call in modrinth.calls),
        )
        self.assertEqual(3, rerun_curseforge.updated)
        self.assertEqual(
            post_count + 3,
            sum(call["method"] == "POST" for call in curseforge.calls),
        )
        for loader in sync.EXPECTED_LOADERS:
            self.assertEqual(
                expected_minecraft_versions,
                modrinth.game_versions[loader],
            )
            self.assertEqual(
                [
                    initial_release.publication.artifacts[
                        loader
                    ].curseforge_loader,
                    *expected_minecraft_versions,
                ],
                curseforge.game_version_names[loader],
            )

    def test_missing_or_incomplete_evidence_never_reaches_a_marketplace(self):
        documents = []

        missing = release_document_with_versions(["26.2"])
        missing["runtime_verification"] = []
        documents.append(missing)

        incomplete = release_document_with_versions(["26.2", "26.3"])
        del incomplete["runtime_verification"][1]["loaders"]["forge"]
        documents.append(incomplete)

        failed = release_document_with_versions(["26.2", "26.3"])
        failed["runtime_verification"][1]["loaders"]["neoforge"][
            "passed"
        ] = False
        documents.append(failed)

        marketplace = FakeClient({})
        for document in documents:
            with self.subTest(document=document):
                with self.assertRaises(sync.PlatformSyncError):
                    release = sync.parse_release_data(document)
                    sync.sync_modrinth(
                        release,
                        "dummy-token",
                        marketplace,
                        base_url="https://modrinth.test/v2",
                    )

        self.assertEqual([], marketplace.calls)


if __name__ == "__main__":
    unittest.main()
