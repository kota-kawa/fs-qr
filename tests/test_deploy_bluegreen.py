import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy_bluegreen.sh"


def test_nginx_upload_limit_accepts_1gib_files_and_upload_envelopes() -> None:
    """nginx がFSQR・Groupの1GiBアップロードをアプリまで通す。"""
    nginx_config = (ROOT / "fs-qr.conf").read_text(encoding="utf-8")

    assert "client_max_body_size 1025M;" in nginx_config
    assert "client_body_timeout 3600s;" in nginx_config


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _base_env(tmp_path: Path, fakebin: Path, nginx_conf: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fakebin}:{env['PATH']}",
            "REPO_DIR": str(tmp_path),
            "NGINX_SITE_CONF": str(nginx_conf),
            "PRIVILEGE_CMD": str(fakebin / "sudo"),
            "NGINX_BIN": str(fakebin / "nginx"),
            "CP_BIN": "/bin/cp",
            "CAT_BIN": "/bin/cat",
            "DRAIN_SECONDS": "0",
            "HEALTH_TIMEOUT": "5",
            "DOCKER_LOG": str(tmp_path / "docker.log"),
            "NGINX_LOG": str(tmp_path / "nginx.log"),
        }
    )
    return env


def _run_deploy_script(
    tmp_path: Path,
    fakebin: Path,
    nginx_conf: Path,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["/usr/bin/bash", str(SCRIPT)],
        env=_base_env(tmp_path, fakebin, nginx_conf),
        text=True,
        capture_output=True,
        check=False,
    )


def _write_docker_stub(fakebin: Path) -> None:
    _write_executable(
        fakebin / "docker",
        """#!/bin/sh
echo "$@" >> "$DOCKER_LOG"
if [ "$1" = "inspect" ]; then
  echo healthy
  exit 0
fi
if [ "$1" = "compose" ] && [ "$4" = "ps" ] && [ "$5" = "-q" ]; then
  echo cid-123
  exit 0
fi
exit 0
""",
    )


def _write_nginx_stub(fakebin: Path, reload_exit: int = 0) -> None:
    _write_executable(
        fakebin / "nginx",
        f"""#!/bin/sh
echo "$@" >> "$NGINX_LOG"
if [ "$1" = "-s" ] && [ "$2" = "reload" ]; then
  exit {reload_exit}
fi
exit 0
""",
    )


def _write_passthrough_sudo(fakebin: Path) -> None:
    _write_executable(
        fakebin / "sudo",
        """#!/bin/sh
exec "$@"
""",
    )


def _write_conf(path: Path) -> None:
    path.write_text(
        """upstream fsqr_app {
    server 127.0.0.1:5000;        # blue (active)
    server 127.0.0.1:5030 down;   # green (standby)
    keepalive 32;
}
"""
    )


def test_deploy_preflight_fails_before_docker_when_sudo_needs_password(
    tmp_path: Path,
) -> None:
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    nginx_conf = tmp_path / "fs-qr.conf"
    _write_conf(nginx_conf)
    _write_docker_stub(fakebin)
    _write_nginx_stub(fakebin)
    _write_executable(
        fakebin / "sudo",
        """#!/bin/sh
echo "sudo: a password is required" >&2
exit 1
""",
    )

    result = _run_deploy_script(tmp_path, fakebin, nginx_conf)

    assert result.returncode != 0
    assert "cannot manage nginx non-interactively" in result.stdout
    assert not (tmp_path / "docker.log").exists()


def test_deploy_switches_nginx_and_stops_old_slot(tmp_path: Path) -> None:
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    deploy_dir = tmp_path / ".deploy"
    deploy_dir.mkdir()
    (deploy_dir / "active_color").write_text("blue\n")
    nginx_conf = tmp_path / "fs-qr.conf"
    _write_conf(nginx_conf)
    _write_docker_stub(fakebin)
    _write_nginx_stub(fakebin)
    _write_passthrough_sudo(fakebin)

    result = _run_deploy_script(tmp_path, fakebin, nginx_conf)

    assert result.returncode == 0, result.stderr + result.stdout
    assert "server 127.0.0.1:5030;        # active" in nginx_conf.read_text()
    assert "server 127.0.0.1:5000 down;   # standby" in nginx_conf.read_text()
    assert (deploy_dir / "active_color").read_text() == "green\n"
    assert (
        "compose --profile blue stop web-blue" in (tmp_path / "docker.log").read_text()
    )


def test_deploy_restores_nginx_conf_and_stops_target_on_reload_failure(
    tmp_path: Path,
) -> None:
    fakebin = tmp_path / "bin"
    fakebin.mkdir()
    deploy_dir = tmp_path / ".deploy"
    deploy_dir.mkdir()
    (deploy_dir / "active_color").write_text("blue\n")
    nginx_conf = tmp_path / "fs-qr.conf"
    _write_conf(nginx_conf)
    original_conf = nginx_conf.read_text()
    _write_docker_stub(fakebin)
    _write_nginx_stub(fakebin, reload_exit=1)
    _write_passthrough_sudo(fakebin)

    result = _run_deploy_script(tmp_path, fakebin, nginx_conf)

    assert result.returncode != 0
    assert nginx_conf.read_text() == original_conf
    assert (deploy_dir / "active_color").read_text() == "blue\n"
    assert (
        "compose --profile green stop web-green"
        in (tmp_path / "docker.log").read_text()
    )
