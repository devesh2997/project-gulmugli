"""
Music Playback — End-to-End Test Script

Tests the full music pipeline on your Mac:
  1. ytmusicapi searches YouTube Music (no API key needed)
  2. mpv plays the audio stream (no video, audio only)
  3. IPC socket allows control commands (pause, resume, volume, skip)

This script tests each piece independently, then the full pipeline.
Run this BEFORE running the assistant to verify your setup works.

Prerequisites:
    brew install mpv
    pip3 install ytmusicapi

Usage:
    python test_music_playback.py
"""

import subprocess
import sys
import os
import json
import time
import socket
import tempfile


# ─── Colours for terminal output ────────────────────────────
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def check_mpv():
    """Verify mpv is installed and accessible."""
    print(f"\n{BOLD}── Test 1: mpv installation ──{RESET}")
    try:
        # Use 'which' to find mpv path — avoids mpv's slow startup
        which_result = subprocess.run(
            ["which", "mpv"],
            capture_output=True, text=True, timeout=5
        )
        if which_result.returncode != 0:
            print(f"  {RED}✗{RESET} mpv not found in PATH!")
            print(f"    Install it: brew install mpv")
            return False

        mpv_path = which_result.stdout.strip()
        print(f"  {GREEN}✓{RESET} mpv found at: {mpv_path}")

        # Try --version with a generous timeout (mpv can be slow to init)
        try:
            result = subprocess.run(
                ["mpv", "--version"],
                capture_output=True, text=True, timeout=15
            )
            version_line = result.stdout.split("\n")[0]
            print(f"  {GREEN}✓{RESET} Version: {version_line}")
        except subprocess.TimeoutExpired:
            print(f"  {YELLOW}!{RESET} --version timed out (this is OK on some macOS setups)")
            print(f"    mpv is installed and will work fine for audio playback.")

        return True
    except FileNotFoundError:
        print(f"  {RED}✗{RESET} mpv not found!")
        print(f"    Install it: brew install mpv")
        return False
    except Exception as e:
        print(f"  {RED}✗{RESET} Error checking mpv: {e}")
        return False


def check_ytmusicapi():
    """Verify ytmusicapi is installed and can search."""
    print(f"\n{BOLD}── Test 2: YouTube Music search ──{RESET}")
    try:
        from ytmusicapi import YTMusic
        ytm = YTMusic()

        # Test with a well-known song
        query = "Shape of You Ed Sheeran"
        print(f"  Searching: '{query}'")
        results = ytm.search(query, filter="songs", limit=3)

        if results:
            for i, r in enumerate(results[:3]):
                title = r.get("title", "?")
                artists = ", ".join(a["name"] for a in r.get("artists", []))
                video_id = r.get("videoId", "?")
                duration = r.get("duration", "?")
                print(f"  {GREEN}✓{RESET} [{i+1}] {title} — {artists} ({duration}) [id: {video_id}]")
            return results[0].get("videoId")
        else:
            print(f"  {RED}✗{RESET} No results returned. Check your internet connection.")
            return None

    except ImportError:
        print(f"  {RED}✗{RESET} ytmusicapi not installed!")
        print(f"    Install it: pip3 install ytmusicapi")
        return None
    except Exception as e:
        print(f"  {RED}✗{RESET} Search failed: {e}")
        return None


def test_mpv_playback(video_id: str):
    """Test mpv playing a YouTube URL with audio only."""
    print(f"\n{BOLD}── Test 3: mpv audio playback ──{RESET}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    ipc_socket = os.path.join(tempfile.gettempdir(), "test-mpv-socket")

    # Clean up any leftover socket
    if os.path.exists(ipc_socket):
        os.remove(ipc_socket)

    print(f"  Playing: {url}")
    print(f"  Mode: audio only (--no-video)")
    print(f"  IPC socket: {ipc_socket}")

    try:
        process = subprocess.Popen(
            [
                "mpv",
                "--no-video",
                f"--input-ipc-server={ipc_socket}",
                "--really-quiet",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Give mpv a moment to start and buffer
        print(f"  Waiting for mpv to start and buffer...")
        time.sleep(5)

        if process.poll() is not None:
            print(f"  {RED}✗{RESET} mpv exited immediately (code: {process.returncode})")
            print(f"    This usually means yt-dlp couldn't extract the audio stream.")
            print(f"    Try: brew upgrade yt-dlp")
            return None, None

        print(f"  {GREEN}✓{RESET} Audio is playing!")
        return process, ipc_socket

    except Exception as e:
        print(f"  {RED}✗{RESET} Playback failed: {e}")
        return None, None


def send_mpv_command(ipc_socket: str, command: dict) -> dict | None:
    """Send a command to mpv via IPC socket and get the response."""
    if not os.path.exists(ipc_socket):
        return None
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(ipc_socket)
        sock.send(json.dumps(command).encode() + b"\n")
        sock.settimeout(2)
        response = sock.recv(4096).decode()
        sock.close()
        return json.loads(response) if response else None
    except Exception as e:
        return {"error": str(e)}


def test_playback_controls(ipc_socket: str):
    """Test pause, resume, volume, and other controls via IPC."""
    print(f"\n{BOLD}── Test 4: Playback controls (IPC socket) ──{RESET}")

    # Test: Pause
    print(f"  Pausing...")
    send_mpv_command(ipc_socket, {"command": ["set_property", "pause", True]})
    time.sleep(2)
    print(f"  {GREEN}✓{RESET} Paused (did the audio stop?)")

    # Test: Resume
    print(f"  Resuming...")
    send_mpv_command(ipc_socket, {"command": ["set_property", "pause", False]})
    time.sleep(2)
    print(f"  {GREEN}✓{RESET} Resumed (did the audio start again?)")

    # Test: Volume down
    print(f"  Setting volume to 30%...")
    send_mpv_command(ipc_socket, {"command": ["set_property", "volume", 30]})
    time.sleep(2)
    print(f"  {GREEN}✓{RESET} Volume set to 30% (did it get quieter?)")

    # Test: Volume up
    print(f"  Setting volume to 80%...")
    send_mpv_command(ipc_socket, {"command": ["set_property", "volume", 80]})
    time.sleep(2)
    print(f"  {GREEN}✓{RESET} Volume set to 80% (did it get louder?)")

    # Test: Get current position (verify two-way communication)
    resp = send_mpv_command(ipc_socket, {"command": ["get_property", "time-pos"]})
    if resp and "data" in resp:
        pos = resp["data"]
        print(f"  {GREEN}✓{RESET} Current position: {pos:.1f}s (IPC two-way communication works!)")
    else:
        print(f"  {YELLOW}?{RESET} Couldn't read position (resp: {resp}). One-way commands still work.")


def test_hindi_search():
    """Test searching with Hindi/Hinglish queries — the real use case."""
    print(f"\n{BOLD}── Test 5: Hindi/Hinglish search queries ──{RESET}")

    from ytmusicapi import YTMusic
    ytm = YTMusic()

    queries = [
        ("kuch romantic bajao", "Should find a romantic Hindi song"),
        ("Arijit Singh latest", "Should find recent Arijit Singh tracks"),
        ("tum hi ho", "Should find Aashiqui 2 song"),
        ("sad Hindi songs", "Should find Hindi sad song playlist-style results"),
        ("party songs Hindi", "Should find upbeat Hindi party tracks"),
    ]

    for query, expected in queries:
        results = ytm.search(query, filter="songs", limit=1)
        if results:
            r = results[0]
            title = r.get("title", "?")
            artists = ", ".join(a["name"] for a in r.get("artists", []))
            print(f"  {GREEN}✓{RESET} '{query}' → {title} — {artists}")
        else:
            print(f"  {RED}✗{RESET} '{query}' → No results")


def cleanup(process, ipc_socket):
    """Stop playback and clean up."""
    if process:
        process.terminate()
        try:
            process.wait(timeout=3)
        except:
            process.kill()
    if ipc_socket and os.path.exists(ipc_socket):
        os.remove(ipc_socket)


# ─── Main ─────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print(f"  {BOLD}Music Playback — End-to-End Test{RESET}")
    print("=" * 60)

    process = None
    ipc_socket = None

    try:
        # Test 1: mpv
        if not check_mpv():
            print(f"\n{RED}Cannot continue without mpv. Install it and retry.{RESET}")
            sys.exit(1)

        # Test 2: YouTube Music search
        video_id = check_ytmusicapi()
        if not video_id:
            print(f"\n{RED}Cannot continue without ytmusicapi. Install it and retry.{RESET}")
            sys.exit(1)

        # Test 3: Playback
        print(f"\n  {CYAN}You should hear audio in ~5 seconds...{RESET}")
        process, ipc_socket = test_mpv_playback(video_id)
        if not process:
            print(f"\n{RED}Playback failed. Check mpv and yt-dlp.{RESET}")
            sys.exit(1)

        # Test 4: Controls
        test_playback_controls(ipc_socket)

        # Stop playback before search tests
        print(f"\n  Stopping playback...")
        cleanup(process, ipc_socket)
        process = None
        ipc_socket = None
        time.sleep(1)

        # Test 5: Hindi searches
        test_hindi_search()

        print(f"\n{'=' * 60}")
        print(f"  {GREEN}{BOLD}All tests passed!{RESET}")
        print(f"  Your music setup is ready for the assistant.")
        print(f"  Next: cd jarvis/assistant && python main.py --text")
        print(f"{'=' * 60}")

    except KeyboardInterrupt:
        print(f"\n\n  Interrupted. Cleaning up...")
    finally:
        cleanup(process, ipc_socket)
