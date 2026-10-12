# APP-004 evidence · 2026-10-12

Isolated synthetic invalid-configuration and recovery experiment. No real secret, user identity or hosted configuration
was changed.

`docker-preflight.json` separately records a real local workstation limitation found during release verification:
Docker Desktop 4.91.0 could not rotate an inaccessible zero-byte AF_UNIX runtime socket. No factory reset, WSL-wide
shutdown or Docker data deletion was attempted. This means the v0.8.0 container is not locally re-verified; the clean
GitHub-hosted Linux build remains a required release gate. Earlier F22 evidence remains the last successful local
non-root container run.
