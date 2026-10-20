import unittest

from scripts.semantic_release import Commit, classify_commit, highest_bump, next_version


class SemanticReleaseTests(unittest.TestCase):
    def test_feat_is_minor(self):
        item = classify_commit(Commit("a" * 40, "feat(client): add retries"))
        self.assertEqual(item.commit_type, "feat")
        self.assertEqual(item.bump, "minor")

    def test_breaking_marker_is_major(self):
        item = classify_commit(Commit("b" * 40, "feat(client)!: remove legacy option"))
        self.assertTrue(item.breaking)
        self.assertEqual(item.bump, "major")

    def test_breaking_footer_is_major(self):
        item = classify_commit(
            Commit(
                "c" * 40,
                "fix(stream): normalize state",
                "BREAKING CHANGE: event shape changed.",
            )
        )
        self.assertEqual(item.bump, "major")

    def test_unknown_type_falls_back_to_chore_patch(self):
        item = classify_commit(Commit("d" * 40, "update: refresh examples"))
        self.assertEqual(item.commit_type, "chore")
        self.assertEqual(item.description, "refresh examples")
        self.assertEqual(item.bump, "patch")

    def test_non_conventional_subject_falls_back_to_chore_patch(self):
        item = classify_commit(Commit("e" * 40, "Refresh examples"))
        self.assertEqual(item.commit_type, "chore")
        self.assertEqual(item.bump, "patch")

    def test_highest_bump_wins(self):
        commits = [
            classify_commit(Commit("f" * 40, "chore: tidy docs")),
            classify_commit(Commit("1" * 40, "feat: add network helper")),
            classify_commit(Commit("2" * 40, "fix!: remove old contract")),
        ]
        self.assertEqual(highest_bump(commits), "major")

    def test_next_version(self):
        self.assertEqual(next_version((0, 0, 0), "patch"), (0, 0, 1))
        self.assertEqual(next_version((0, 0, 1), "minor"), (0, 1, 0))
        self.assertEqual(next_version((0, 1, 0), "major"), (1, 0, 0))


if __name__ == "__main__":
    unittest.main()
