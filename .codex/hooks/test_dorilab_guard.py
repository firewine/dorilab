from __future__ import annotations

import unittest

from dorilab_guard import destructive_reason


class DoriLabGuardTest(unittest.TestCase):
    def test_blocks_project_data_and_global_docker_destructive_commands(self) -> None:
        self.assertIsNotNone(destructive_reason("docker compose down -v"))
        self.assertIsNotNone(destructive_reason("docker system prune -af"))
        self.assertIsNotNone(destructive_reason("docker volume rm dorilab-postgres"))
        self.assertIsNotNone(destructive_reason("docker context use remote-prod"))

    def test_blocks_history_rewrite_and_broad_delete(self) -> None:
        self.assertIsNotNone(destructive_reason("git reset --hard HEAD~1"))
        self.assertIsNotNone(destructive_reason("git push --force-with-lease origin main"))
        self.assertIsNotNone(destructive_reason("rm -rf /"))

    def test_blocks_runpod_and_ssh_boundary_bypass(self) -> None:
        self.assertIsNotNone(destructive_reason("ssh -o StrictHostKeyChecking=no root@pod"))
        self.assertIsNotNone(destructive_reason("ssh -A root@pod"))
        self.assertIsNotNone(destructive_reason("runpodctl stop pod-id"))

    def test_allows_normal_dorilab_development(self) -> None:
        allowed = (
            "./scripts/dev.sh setup",
            "./scripts/dev.sh up --demo",
            "./scripts/dev.sh test",
            "docker compose config",
            "docker compose down --remove-orphans",
            "docker compose logs --tail=200 api worker llm-tunnel",
            "git diff --check",
            "git push origin feature/dorilab",
            "rm -rf /private/tmp/dorilab-test-123",
            "ssh -a root@pod",
            "ssh -o StrictHostKeyChecking=yes -o ForwardAgent=no root@pod",
        )
        for command in allowed:
            with self.subTest(command=command):
                self.assertIsNone(destructive_reason(command))


if __name__ == "__main__":
    unittest.main()
