"""
SFTP Inbound GMF Poller — Method A.

Connects to a remote SLT VM via SFTP on a configurable schedule (default: every
1 second using a persistent connection) and downloads new GMF / spreadsheet files
into the local GMF upload folders where the existing watcher automatically
detects, identifies, and registers them.
"""

import logging
import os
import stat
import threading
import time
from pathlib import Path

import paramiko

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Remote-to-local folder mapping ──────────────────────────────────────────────
# Keys   = subfolder names expected on the remote SLT VM
# Values = subfolder names under settings.gmf_drive_path on our VM
REMOTE_TO_LOCAL_FOLDER: dict[str, str] = {
    "Cycle":              "Cycle",
    "LOD":                "LOD",
    "VAT_Confirmation":   "VAT_Confirmation",
    "Final_Notice":       "Final_Notice",
    "Customer_Letter":    "Customer_Letter",
    "Test_GMFs":          "Test_GMFs",
}

# ── File filtering (same rules as watcher.py) ──────────────────────────────────
_SKIP_PREFIXES = (".", "~", "__")
_SKIP_SUFFIXES = (".tmp", ".part", ".partial", ".crdownload", ".downloading")
_SKIP_NAMES = {"desktop.ini", "thumbs.db"}


def _should_skip(filename: str) -> bool:
    """Return True if this file should be ignored (temp / system files)."""
    name = filename.lower()
    if name in _SKIP_NAMES:
        return True
    if any(name.startswith(p) for p in _SKIP_PREFIXES):
        return True
    if any(name.endswith(s) for s in _SKIP_SUFFIXES):
        return True
    ext = os.path.splitext(name)[1].lower()
    ext_clean = ext[1:] if ext.startswith(".") else ext
    # Accept: no extension, numeric extensions (.1-.99), .gmf, .xlsx, .xls, .csv
    if ext_clean and ext_clean not in ("gmf", "xlsx", "xls", "csv", "zip") and not ext_clean.isdigit():
        return True
    return False


def _connect_sftp() -> tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    """Establish an SSH + SFTP connection to the remote host."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    connect_kwargs: dict = {
        "hostname": settings.sftp_host,
        "port": settings.sftp_port,
        "username": settings.sftp_username,
        "timeout": 10,
    }

    if settings.sftp_key_path and os.path.exists(settings.sftp_key_path):
        connect_kwargs["key_filename"] = settings.sftp_key_path
    elif settings.sftp_password:
        connect_kwargs["password"] = settings.sftp_password
    else:
        # Try agent-based auth (ssh-agent keys)
        connect_kwargs["allow_agent"] = True
        connect_kwargs["look_for_keys"] = True

    ssh.connect(**connect_kwargs)
    sftp = ssh.open_sftp()
    return ssh, sftp


def _ensure_remote_processed_dir(sftp: paramiko.SFTPClient, remote_subfolder: str) -> str:
    """Ensure a 'processed/' subdirectory exists inside the remote subfolder."""
    processed_path = remote_subfolder.rstrip("/") + "/processed"
    try:
        sftp.stat(processed_path)
    except FileNotFoundError:
        try:
            sftp.mkdir(processed_path)
        except IOError:
            pass  # May already exist from a race condition
    return processed_path


def _list_remote_files(sftp: paramiko.SFTPClient, remote_dir: str) -> list[str]:
    """List regular files in a remote directory, skipping subdirectories."""
    try:
        entries = sftp.listdir_attr(remote_dir)
    except FileNotFoundError:
        return []
    return [
        entry.filename
        for entry in entries
        if stat.S_ISREG(entry.st_mode or 0)
        and not _should_skip(entry.filename)
    ]


def _poll_once(sftp: paramiko.SFTPClient, seen_files: dict[str, set[str]]) -> int:
    """
    Run a single poll cycle: scan all remote subfolders, download new files,
    and move them to processed/ on the remote side.

    Returns the number of files downloaded in this cycle.
    """
    remote_root = settings.sftp_remote_dir.rstrip("/")
    local_root = Path(str(settings.gmf_drive_path))
    downloaded = 0

    for remote_folder, local_folder in REMOTE_TO_LOCAL_FOLDER.items():
        remote_path = f"{remote_root}/{remote_folder}"

        # List files on the remote side
        try:
            filenames = _list_remote_files(sftp, remote_path)
        except Exception as e:
            logger.debug(f"SFTP: Could not list {remote_path}: {e}")
            continue

        if not filenames:
            continue

        # Ensure local target folder exists
        local_target = local_root / local_folder
        local_target.mkdir(parents=True, exist_ok=True)

        # Track which files we have already seen in this folder
        if remote_folder not in seen_files:
            seen_files[remote_folder] = set()

        for filename in filenames:
            if filename in seen_files[remote_folder]:
                continue

            remote_file = f"{remote_path}/{filename}"
            local_file = local_target / filename
            temp_file = local_target / f"{filename}.downloading"

            try:
                # Download atomically: write to .downloading, then rename
                sftp.get(remote_file, str(temp_file))
                if temp_file.exists():
                    if local_file.exists():
                        local_file.unlink()
                    temp_file.rename(local_file)

                # Move remote file to processed/ subfolder
                processed_dir = _ensure_remote_processed_dir(sftp, remote_path)
                try:
                    sftp.rename(remote_file, f"{processed_dir}/{filename}")
                except IOError:
                    # If rename fails (e.g. cross-device), just leave it
                    pass

                seen_files[remote_folder].add(filename)
                downloaded += 1
                logger.info(
                    f"SFTP: Downloaded '{filename}' from "
                    f"{remote_folder}/ -> {local_folder}/"
                )
            except Exception as e:
                logger.warning(f"SFTP: Failed to download {remote_file}: {e}")
                # Clean up partial download
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass

    return downloaded


def _poller_loop():
    """
    Main polling loop — maintains a persistent SFTP connection and polls
    every N seconds.  Reconnects automatically on connection loss.
    """
    interval = max(0.5, settings.sftp_poll_interval_seconds)
    seen_files: dict[str, set[str]] = {}
    ssh: paramiko.SSHClient | None = None
    sftp: paramiko.SFTPClient | None = None
    backoff = 1  # seconds, for reconnection backoff

    logger.info(
        f"SFTP Poller started — polling {settings.sftp_host}:{settings.sftp_port} "
        f"every {interval}s (remote dir: {settings.sftp_remote_dir})"
    )

    while True:
        try:
            # Establish or re-establish connection
            if sftp is None or ssh is None or not ssh.get_transport() or not ssh.get_transport().is_active():
                if ssh:
                    try:
                        ssh.close()
                    except Exception:
                        pass
                logger.info(f"SFTP: Connecting to {settings.sftp_host}:{settings.sftp_port}...")
                ssh, sftp = _connect_sftp()
                backoff = 1  # Reset backoff on successful connection
                logger.info(f"SFTP: Connected successfully.")

            # Run one poll cycle
            _poll_once(sftp, seen_files)

        except paramiko.AuthenticationException as e:
            logger.error(f"SFTP: Authentication failed — check credentials: {e}")
            sftp = None
            ssh = None
            time.sleep(min(backoff, 60))
            backoff = min(backoff * 2, 60)

        except Exception as e:
            logger.warning(f"SFTP: Connection error — will retry in {backoff}s: {e}")
            sftp = None
            ssh = None
            time.sleep(min(backoff, 30))
            backoff = min(backoff * 2, 30)
            continue

        time.sleep(interval)


def start_sftp_poller():
    """Launch the SFTP poller as a background daemon thread."""
    if not settings.sftp_enabled:
        logger.info("SFTP Poller is disabled (SFTP_ENABLED=false). Skipping.")
        return

    thread = threading.Thread(target=_poller_loop, daemon=True, name="sftp-poller")
    thread.start()
    logger.info("SFTP Poller daemon thread started.")
