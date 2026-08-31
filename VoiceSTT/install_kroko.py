"""
Build and install Kroko-ONNX for the active VoiceSTT environment.
"""

from __future__ import print_function

import argparse
import json
import os
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

from VoiceSTT.kroko import artifacts as kroko_artifacts
from VoiceSTT.kroko import buildinputs
from VoiceSTT.kroko import fingerprint as kroko_fingerprint


DEFAULT_REPO = buildinputs.KROKO_UPSTREAM_REPO
# AP-SRV-070 W4A: the branch is only a starting point for the clone. The build
# authority is the immutable revision below - a build must never silently
# follow a moving branch head.
DEFAULT_BRANCH = buildinputs.KROKO_UPSTREAM_BRANCH_HINT
DEFAULT_REVISION = buildinputs.KROKO_UPSTREAM_REVISION
SUPPORTED_VARIANTS = buildinputs.SUPPORTED_VARIANTS
KROKO_LICENSE_QUIET_ENV = "KROKO_ONNX_SUPPRESS_LICENSE_OUTPUT"


class KrokoInstallError(RuntimeError):
    """
    Reports Kroko installation failures.
    """

    pass


def parse_args(argv=None):
    """
    Parses command-line arguments for Kroko installation.
    """

    parser = argparse.ArgumentParser(
        prog="stt-install-kroko",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Build and install Kroko-ONNX for the active Python environment. "
            "Windows builds a wheel with Kroko's Docker workflow; Linux installs "
            "from the upstream source checkout."
        ),
        epilog=(
            "Platform note:\n"
            "  VoiceSTT core supports Python 3.11+.\n"
            "  On Windows, stt-install-kroko --build currently requires "
            "CPython 3.12 x64.\n"
            "  Use the same Python 3.12 x64 environment for the builder and "
            "Kroko runtime."
        ),
    )
    parser.add_argument(
        "--build",
        action="store_true",
        help="Build/install Kroko-ONNX from the upstream source checkout.",
    )
    parser.add_argument(
        "--variant",
        choices=SUPPORTED_VARIANTS,
        default="free",
        help="Build the free community runtime or the licensed pro runtime.",
    )
    parser.add_argument(
        "--repo",
        default=DEFAULT_REPO,
        help="Kroko-ONNX git repository URL.",
    )
    parser.add_argument(
        "--branch",
        default=DEFAULT_BRANCH,
        help=(
            "Kroko-ONNX git branch used to seed the clone. The build itself "
            "checks out the pinned revision, not this branch's head."
        ),
    )
    parser.add_argument(
        "--revision",
        default=DEFAULT_REVISION,
        help=(
            "Immutable Kroko-ONNX commit to build. Defaults to the revision "
            "pinned in VoiceSTT.kroko.buildinputs; overriding it changes the "
            "build fingerprint and therefore requires its own artifact."
        ),
    )
    parser.add_argument(
        "--artifact-store",
        default=None,
        help=(
            "Root of the persistent Kroko artifact store. Defaults to "
            "${0} or the per-user cache directory.".format(
                kroko_artifacts.ARTIFACT_STORE_ENV
            )
        ),
    )
    parser.add_argument(
        "--rebuild-kroko",
        action="store_true",
        help=(
            "Force a real native rebuild even when a matching verified "
            "artifact exists, then atomically replace the stored artifact. "
            "Without this flag a matching artifact is reused and nothing is "
            "compiled."
        ),
    )
    parser.add_argument(
        "--print-fingerprint",
        action="store_true",
        help="Print the build fingerprint as JSON and exit. Compiles nothing.",
    )
    parser.add_argument(
        "--describe-artifact",
        action="store_true",
        help=(
            "Print the fingerprint plus whether a verified artifact exists in "
            "the store, as JSON, and exit. Compiles nothing."
        ),
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help=(
            "Directory used for the Kroko-ONNX checkout and build artifacts. "
            "If omitted and the default cache is not writable, a project-local "
            "kroko-builder-work directory is used."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete the existing builder checkout before cloning again.",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Build only; do not install the produced package into this Python.",
    )
    return parser.parse_args(argv)


def quote_cmd(cmd):
    """
    Formats a command for readable logging.
    """

    if os.name == "nt":
        return subprocess.list2cmdline([str(part) for part in cmd])
    return " ".join(shlex.quote(str(part)) for part in cmd)


def run(cmd, cwd=None, env=None):
    """
    Runs a subprocess command and reports failures.
    """

    print("+ " + quote_cmd(cmd))
    try:
        subprocess.check_call(
            [str(part) for part in cmd],
            cwd=str(cwd) if cwd is not None else None,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        raise KrokoInstallError(
            "Command failed with exit code {0}: {1}".format(
                exc.returncode,
                quote_cmd(cmd),
            )
        )


def ensure_program(name, message):
    """
    Verifies that a required program is available.
    """

    if shutil.which(name) is None:
        raise KrokoInstallError(message)


def default_work_dir():
    """
    Returns the default Kroko builder work directory.
    """

    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "VoiceSTT" / "kroko-builder"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "VoiceSTT" / "kroko-builder"
    else:
        root = os.environ.get("XDG_CACHE_HOME")
        if root:
            return Path(root) / "voicestt" / "kroko-builder"
    return Path(tempfile.gettempdir()) / "voicestt-kroko-builder"


def resolve_work_dir(args):
    """
    Resolves the Kroko builder work directory.
    """

    if args.work_dir is not None:
        return args.work_dir.expanduser().resolve()

    work_dir = default_work_dir().expanduser().resolve()
    try:
        ensure_work_dir_writable(work_dir)
        return work_dir
    except KrokoInstallError as exc:
        fallback = (Path.cwd() / "kroko-builder-work").resolve()
        print(
            "Default Kroko builder cache is not writable; using project-local "
            "work directory instead:\n"
            "    {0}\n"
            "Use --work-dir to choose a different location.\n"
            "Original error: {1}".format(fallback, exc),
            file=sys.stderr,
        )
        ensure_work_dir_writable(fallback)
        return fallback


def ensure_work_dir_writable(work_dir):
    """
    Verifies that the builder work directory is writable.
    """

    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        probe = work_dir / ".voicestt-kroko-write-test"
        with probe.open("w", encoding="utf-8") as handle:
            handle.write("ok")
        probe.unlink()
    except OSError as exc:
        raise KrokoInstallError(
            "Kroko builder work directory is not writable: {0}\n"
            "Choose a writable directory with:\n"
            "    stt-install-kroko --build --work-dir .\\kroko-builder-work\n"
            "Original error: {1}".format(work_dir, exc)
        )


def preflight_build(args):
    """
    Checks host prerequisites before building Kroko.
    """

    ensure_program("git", "Git is required to download Kroko-ONNX.")
    work_dir = resolve_work_dir(args)
    ensure_work_dir_writable(work_dir)

    if os.name == "nt":
        ensure_windows_host()
    elif sys.platform.startswith("linux"):
        ensure_program("cmake", "CMake is required to build Kroko-ONNX from source on Linux.")

    return work_dir


def remove_tree_inside(path, root):
    """
    Removes a directory tree after validating its parent root.
    """

    path = path.resolve()
    root = root.resolve()
    if path == root or root not in path.parents:
        raise KrokoInstallError("Refusing to remove path outside builder cache: {0}".format(path))

    def clear_readonly(func, failed_path, _exc_info):
        """
        Clears read-only file attributes during tree removal.
        """

        os.chmod(failed_path, stat.S_IWRITE)
        func(failed_path)

    shutil.rmtree(str(path), onerror=clear_readonly)


def prepare_checkout(args, work_dir=None):
    """
    Prepares the Kroko source checkout.
    """

    work_dir = work_dir or resolve_work_dir(args)
    repo_dir = work_dir / "kroko-onnx"
    ensure_work_dir_writable(work_dir)

    if args.force and repo_dir.exists():
        print("Removing existing Kroko-ONNX checkout: {0}".format(repo_dir))
        remove_tree_inside(repo_dir, work_dir)

    if not repo_dir.exists():
        run(
            [
                "git",
                "-c",
                "core.autocrlf=false",
                "clone",
                "--branch",
                args.branch,
                "--single-branch",
                args.repo,
                str(repo_dir),
            ]
        )
    else:
        print("Using existing Kroko-ONNX checkout: {0}".format(repo_dir))
        print("Pass --force to delete and clone it again.")

    ensure_pinned_revision(repo_dir, getattr(args, "revision", DEFAULT_REVISION))
    return repo_dir


def current_revision(repo_dir):
    """
    Returns the commit currently checked out in the Kroko checkout.
    """

    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_dir),
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        raise KrokoInstallError(
            "Could not read the Kroko checkout revision in {0}: {1}".format(repo_dir, exc)
        )
    return output.decode("utf-8", "replace").strip()


def ensure_pinned_revision(repo_dir, revision):
    """
    Checks the pinned immutable Kroko revision out.

    A build must be reproducible, so it never uses whatever the branch head
    happens to be. If the pinned commit is not in the local clone yet - the
    usual case for a shallow or single-branch clone - it is fetched explicitly.
    """

    revision = str(revision).strip()
    if not revision:
        raise KrokoInstallError("No Kroko upstream revision is pinned.")

    if current_revision(repo_dir) == revision:
        return revision

    print("Checking out pinned Kroko revision: {0}".format(revision))
    try:
        run(["git", "checkout", "--detach", revision], cwd=repo_dir)
    except KrokoInstallError:
        run(["git", "fetch", "--tags", "origin", revision], cwd=repo_dir)
        run(["git", "checkout", "--detach", revision], cwd=repo_dir)

    checked_out = current_revision(repo_dir)
    if checked_out != revision:
        raise KrokoInstallError(
            "Kroko checkout is at {0}, but the pinned revision is {1}.".format(
                checked_out,
                revision,
            )
        )
    return checked_out


def read_text(path):
    """
    Reads a UTF-8 text file.
    """

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        return handle.read()


def write_text(path, text):
    """
    Writes a UTF-8 text file.
    """

    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def normalize_lf(path):
    """
    Normalizes a text file to LF line endings.
    """

    data = path.read_bytes()
    normalized = data.replace(b"\r\n", b"\n")
    if normalized != data:
        path.write_bytes(normalized)
        print("Normalized LF line endings: {0}".format(path.name))


def sanitize_batch_ascii(path):
    """
    Replaces non-ASCII batch file characters with safe text.
    """

    text = read_text(path)
    sanitized = "".join(char if ord(char) < 128 else "-" for char in text)
    if sanitized != text:
        with path.open("w", encoding="ascii", newline="") as handle:
            handle.write(sanitized)
        print("Normalized build_windows.bat to ASCII for cmd.exe.")


def patch_windows_bat(repo_dir):
    """
    Patches the Kroko Windows build batch file.
    """

    path = repo_dir / "build_windows.bat"
    if not path.exists():
        raise KrokoInstallError("Missing Kroko Windows build script: {0}".format(path))

    text = read_text(path)
    if 'findstr /C:"set(SHERPA_ONNX_VERSION"' in text:
        return
    if "Select-String" not in text or "SHERPA_ONNX_VERSION" not in text:
        print("Could not identify Kroko version parser in build_windows.bat; leaving it unchanged.")
        return

    start = text.find('REM CMakeLists has:  set(SHERPA_ONNX_VERSION "1.12.9")')
    if start == -1:
        start = text.find("set \"VERSION=\"")
    if start == -1:
        print("Could not identify Kroko version parser in build_windows.bat; leaving it unchanged.")
        return

    if_pos = text.find('if "%VERSION%"==""', start)
    if if_pos == -1:
        print("Could not identify Kroko version parser in build_windows.bat; leaving it unchanged.")
        return

    block_end = text.rfind("\n", 0, if_pos) + 1
    newline = "\r\n" if "\r\n" in text else "\n"
    replacement = newline.join(
        [
            'REM CMakeLists has:  set(SHERPA_ONNX_VERSION "1.12.9")',
            "REM Keep this pure batch so cmd.exe does not parse nested PowerShell regex",
            "REM parentheses inside a FOR command substitution.",
            'set "VERSION="',
            'for /f "tokens=2 delims= " %%v in (\'findstr /C:"set(SHERPA_ONNX_VERSION" "%ROOT%\\CMakeLists.txt"\') do set "VERSION=%%~v"',
            'set "VERSION=%VERSION:"=%"',
            'set "VERSION=%VERSION:)=%"',
            "",
        ]
    )
    write_text(path, text[:start] + replacement + text[block_end:])
    print("Patched build_windows.bat version parsing for cmd.exe.")


def patch_windows_dockerfile(repo_dir):
    """
    Patches the Kroko Windows Dockerfile.
    """

    path = repo_dir / "Dockerfile.windows"
    if not path.exists():
        raise KrokoInstallError("Missing Kroko Windows Dockerfile: {0}".format(path))

    text = read_text(path)
    changed = False

    openssl_start = text.find("# Windows-native OpenSSL")
    openssl_end = text.find("ENV OPENSSL_ROOT_DIR=", openssl_start)
    if openssl_start != -1 and openssl_end != -1:
        newline = "\r\n" if "\r\n" in text else "\n"
        openssl_block = newline.join(
            [
                "# Windows-native OpenSSL - required by sherpa-onnx's CMakeLists when",
                "# SHERPA_ONNX_ENABLE_WEBSOCKET=ON (websocketpp uses it for wss:// support",
                "# and the link is unconditional). Slproweb no longer keeps the previously",
                "# pinned MSI files online reliably, so download the current Inno Setup EXE",
                "# installers and extract the DLLs, import libraries, and headers directly.",
                "RUN apt-get update && apt-get install -y --no-install-recommends \\",
                "        curl innoextract \\",
                " && rm -rf /var/lib/apt/lists/* \\",
                " && mkdir -p /tmp/openssl-final /opt/openssl-win64/app/bin \\",
                "        /opt/openssl-win64/app/lib /opt/openssl-win64/app/include \\",
                " && cd /tmp \\",
                " && for v in 3_6_3 3_5_7 3_4_6 3_0_21; do \\",
                "        for flavor in \"\" \"_Light\"; do \\",
                "            if curl -sLf \"https://slproweb.com/download/Win64OpenSSL${flavor}-${v}.exe\" \\",
                "                    -o openssl.exe; then \\",
                "                echo \"Downloaded Win64OpenSSL${flavor}-${v}.exe\"; \\",
                "                break 2; \\",
                "            fi; \\",
                "            rm -f openssl.exe; \\",
                "        done; \\",
                "    done \\",
                " && test -s openssl.exe \\",
                " && innoextract -d /tmp/openssl-final openssl.exe \\",
                " && (cp -r /tmp/openssl-final/app/* /opt/openssl-win64/app/ 2>/dev/null \\",
                "     || (find /tmp/openssl-final -name \"libcrypto*.dll\" \\",
                "            -exec cp -v {} /opt/openssl-win64/app/bin/ \\; ; \\",
                "         find /tmp/openssl-final -name \"libssl*.dll\" \\",
                "            -exec cp -v {} /opt/openssl-win64/app/bin/ \\; ; \\",
                "         find /tmp/openssl-final -name \"libcrypto.lib\" \\",
                "            -exec cp -v {} /opt/openssl-win64/app/lib/ \\; ; \\",
                "         find /tmp/openssl-final -name \"libssl.lib\" \\",
                "            -exec cp -v {} /opt/openssl-win64/app/lib/ \\; ; \\",
                "         find /tmp/openssl-final -type d -name \"include\" \\",
                "            -exec cp -r {} /opt/openssl-win64/app/ \\;)) \\",
                " && (test -d /opt/openssl-win64/app/lib/VC/x64/MT \\",
                "     && mv /opt/openssl-win64/app/lib/VC/x64/MT/* /opt/openssl-win64/app/lib/ \\",
                "     || true) \\",
                " && test -f /opt/openssl-win64/app/lib/libcrypto.lib \\",
                "        -o -f /opt/openssl-win64/app/lib/libcrypto_static.lib \\",
                " && rm -rf /tmp/openssl-final /tmp/openssl.exe",
                "",
            ]
        )
        if text[openssl_start:openssl_end] != openssl_block:
            text = text[:openssl_start] + openssl_block + text[openssl_end:]
            changed = True
            print("Patched Dockerfile.windows to use current Slproweb OpenSSL EXE installers.")

    if "sed -i 's/\\r$//'" in text:
        if changed:
            write_text(path, text)
        return

    old_lf = (
        "COPY in_windows_container.sh /usr/local/bin/in_windows_container.sh\n"
        "RUN chmod +x /usr/local/bin/in_windows_container.sh"
    )
    new_lf = (
        "COPY in_windows_container.sh /usr/local/bin/in_windows_container.sh\n"
        "RUN sed -i 's/\\r$//' /usr/local/bin/in_windows_container.sh \\\n"
        " && chmod +x /usr/local/bin/in_windows_container.sh"
    )
    old_crlf = old_lf.replace("\n", "\r\n")
    new_crlf = new_lf.replace("\n", "\r\n")
    if old_lf in text:
        text = text.replace(old_lf, new_lf)
        changed = True
        print("Patched Dockerfile.windows to tolerate CRLF shell scripts.")
    elif old_crlf in text:
        text = text.replace(old_crlf, new_crlf)
        changed = True
        print("Patched Dockerfile.windows to tolerate CRLF shell scripts.")
    if changed:
        write_text(path, text)


def patch_windows_container_script(repo_dir):
    """
    Restores the WebSocket settings required by Kroko's Windows build.
    """

    path = repo_dir / "in_windows_container.sh"
    if not path.exists():
        raise KrokoInstallError("Missing Kroko container build script: {0}".format(path))

    text = read_text(path)
    original = text
    newline = "\r\n" if "\r\n" in text else "\n"
    malformed = (
        "    -DSHERPA_ONNX_ENABLE_WEBSOCKET=OFF \\    "
        "-DSHERPA_ONNX_ENABLE_TTS=OFF \\"
    )
    replacement = (
        "    -DSHERPA_ONNX_ENABLE_WEBSOCKET=ON \\" + newline
        + "    -DSHERPA_ONNX_ENABLE_TTS=OFF \\"
    )
    text = text.replace(malformed, replacement)
    text = text.replace(
        "-DSHERPA_ONNX_ENABLE_WEBSOCKET=OFF",
        "-DSHERPA_ONNX_ENABLE_WEBSOCKET=ON",
    )

    linux_openssl_lines = (
        "-DOPENSSL_CRYPTO_LIBRARY=/usr/lib/x86_64-linux-gnu/libcrypto.so.3",
        "-DOPENSSL_SSL_LIBRARY=/usr/lib/x86_64-linux-gnu/libssl.so.3",
    )
    text = "".join(
        line
        for line in text.splitlines(True)
        if not any(marker in line for marker in linux_openssl_lines)
    )

    if text != original:
        write_text(path, text)
        print("Patched in_windows_container.sh for the required Windows WebSocket build.")


def _insert_after_line(text, line_text, insertion):
    """
    Inserts text after a matching source line.
    """

    lines = text.splitlines(True)
    for index, line in enumerate(lines):
        if line.strip() == line_text:
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            if insertion in text:
                return text
            lines.insert(index + 1, insertion.replace("\n", newline))
            return "".join(lines)
    return text


def _wrap_license_output_line(text, marker):
    """
    Wraps license output behind the quiet-mode environment flag.
    """

    lines = text.splitlines(True)
    changed = False
    for index, line in enumerate(lines):
        if marker not in line:
            continue
        if "std::cout" not in line and "std::cerr" not in line:
            continue
        previous = "".join(lines[max(0, index - 2):index])
        if "KrokoSuppressLicenseOutput" in previous:
            continue

        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        content = line.rstrip("\r\n")
        indent = content[:len(content) - len(content.lstrip())]
        statement = content[len(indent):]
        lines[index] = (
            indent + "if (!KrokoSuppressLicenseOutput()) {" + newline
            + indent + "    " + statement + newline
            + indent + "}" + newline
        )
        changed = True

    if not changed:
        return text
    return "".join(lines)


def patch_license_quiet_env(repo_dir):
    """
    Patches Kroko sources to support quiet license output.
    """

    path = repo_dir / "sherpa-onnx" / "csrc" / "license.h"
    if not path.exists():
        print("Could not find Kroko license client source; native license logs may remain noisy.")
        return

    text = read_text(path)
    original = text

    if "#include <cstdlib>" not in text:
        text = _insert_after_line(text, "#include <chrono>", "#include <cstdlib>\n")
    if "#include <windows.h>" not in text:
        text = _insert_after_line(
            text,
            "#include <cstdlib>",
            "#ifdef _WIN32\n#include <windows.h>\n#endif\n",
        )

    helper = (
        "inline std::string KrokoLicenseQuietEnvValue() {\n"
        "#ifdef _WIN32\n"
        "    char buffer[64];\n"
        "    DWORD size = GetEnvironmentVariableA(\n"
        "        \"" + KROKO_LICENSE_QUIET_ENV + "\",\n"
        "        buffer,\n"
        "        static_cast<DWORD>(sizeof(buffer)));\n"
        "    if (size > 0) {\n"
        "        if (size < sizeof(buffer)) {\n"
        "            return std::string(buffer, size);\n"
        "        }\n"
        "        return \"1\";\n"
        "    }\n"
        "#endif\n"
        "\n"
        "    const char* value = std::getenv(\"" + KROKO_LICENSE_QUIET_ENV + "\");\n"
        "    if (value == nullptr) {\n"
        "        return \"\";\n"
        "    }\n"
        "    return std::string(value);\n"
        "}\n\n"
        "inline bool KrokoSuppressLicenseOutput() {\n"
        "    std::string text = KrokoLicenseQuietEnvValue();\n"
        "    return !text.empty() && text != \"0\" && text != \"false\" && text != \"False\" && text != \"FALSE\";\n"
        "}\n\n"
    )
    helper_start = text.find("inline bool KrokoSuppressLicenseOutput() {")
    if helper_start != -1:
        block_start = text.rfind("\ninline ", 0, helper_start)
        if block_start == -1:
            block_start = helper_start
        else:
            block_start += 1
        block_end = text.find("struct Feature {", helper_start)
        if block_end != -1:
            text = text[:block_start] + helper + text[block_end:]
    elif KROKO_LICENSE_QUIET_ENV not in text:
        text = _insert_after_line(text, "using json = nlohmann::json;", "\n" + helper)

    for marker in (
        "License not allowed:",
        "License accepted. Remaining seconds:",
        "Usage report error:",
        "Remaining seconds updated:",
        "JSON parse error:",
        "Connected to license server.",
        "Connection closed.",
        "Connection failed.",
        "Failed to create connection:",
        "Retrying connection in 3s...",
        "Cannot send usage: license not allowed.",
        "No active WebSocket connection.",
        "Failed to send usage report:",
        "Offline timeout exceeded (",
    ):
        text = _wrap_license_output_line(text, marker)

    if text != original:
        write_text(path, text)
        print("Patched Kroko license client to honor {0}.".format(KROKO_LICENSE_QUIET_ENV))


def prepare_windows_checkout(repo_dir):
    """
    Prepares Windows-specific Kroko build files.
    """

    script = repo_dir / "in_windows_container.sh"
    if not script.exists():
        raise KrokoInstallError("Missing Kroko container build script: {0}".format(script))
    normalize_lf(script)
    patch_windows_container_script(repo_dir)
    patch_windows_bat(repo_dir)
    sanitize_batch_ascii(repo_dir / "build_windows.bat")
    patch_windows_dockerfile(repo_dir)
    patch_license_quiet_env(repo_dir)


def ensure_windows_host():
    """
    Verifies that the current host is Windows.
    """

    if sys.version_info[:2] != (3, 12):
        raise KrokoInstallError(
            "Kroko's current Windows wheel build targets CPython 3.12 x64.\n"
            "Your active Python is {0}.{1}.{2} ({3}-bit).\n"
            "VoiceSTT core supports Python 3.11+, but this Kroko Windows "
            "builder path does not.\n"
            "Create and activate a Python 3.12 x64 environment, install "
            "VoiceSTT[kroko-builder] there, then rerun:\n"
            "    stt-install-kroko --build".format(
                sys.version_info.major,
                sys.version_info.minor,
                sys.version_info.micro,
                64 if sys.maxsize > 2 ** 32 else 32,
            )
        )
    if sys.maxsize <= 2 ** 32:
        raise KrokoInstallError(
            "Kroko's current Windows wheel build targets CPython 3.12 x64.\n"
            "Your active Python is 32-bit.\n"
            "Create and activate a 64-bit Python 3.12 environment, install "
            "VoiceSTT[kroko-builder] there, then rerun:\n"
            "    stt-install-kroko --build"
        )
    machine = platform.machine().lower()
    if machine not in ("amd64", "x86_64"):
        raise KrokoInstallError(
            "Kroko's current Windows wheel build targets win_amd64; "
            "this machine reports {0}.".format(platform.machine())
        )
    ensure_program(
        "docker",
        "Docker Desktop is required on Windows. Install Docker Desktop, start it "
        "with the WSL2 backend enabled, then retry.",
    )
    try:
        run(["docker", "version"])
    except KrokoInstallError:
        raise KrokoInstallError(
            "Docker Desktop is not running or its Linux engine is unavailable.\n"
            "Start Docker Desktop, wait until it reports that Docker is running, "
            "then retry:\n"
            "    stt-install-kroko --build\n"
            "You can verify it manually with:\n"
            "    docker version"
        )


def find_windows_wheel(repo_dir, variant):
    """
    Finds the built Kroko Windows wheel.
    """

    tag = "cp{0}{1}".format(sys.version_info.major, sys.version_info.minor)
    wheel_dir = repo_dir / "release_artifacts" / "windows"
    patterns = [
        "kroko_onnx-*-1{0}-{1}-{1}-win_amd64.whl".format(variant, tag),
        "kroko_onnx-*-{0}-{1}-{1}-win_amd64.whl".format(variant, tag),
        "kroko_onnx-*-{0}-{0}-win_amd64.whl".format(tag),
    ]
    wheels = []
    for pattern in patterns:
        wheels.extend(wheel_dir.glob(pattern))
    wheels = sorted(set(wheels), key=lambda item: item.stat().st_mtime, reverse=True)
    if not wheels:
        raise KrokoInstallError(
            "Windows build finished, but no Kroko wheel matching {0}/{1} was found in {2}.".format(
                variant,
                tag,
                wheel_dir,
            )
        )
    return wheels[0]


def install_windows(args, repo_dir):
    """
    Builds and installs Kroko on Windows.
    """

    ensure_windows_host()
    prepare_windows_checkout(repo_dir)
    run(["cmd.exe", "/c", str(repo_dir / "build_windows.bat"), "--variant", args.variant], cwd=repo_dir)
    wheel = find_windows_wheel(repo_dir, args.variant)
    print("Built Kroko-ONNX wheel: {0}".format(wheel))
    if not args.skip_install:
        run([sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheel)])


def linux_build_env(variant):
    """
    Builds the Linux Kroko build environment from the declared build inputs.

    The CMake/make flags come from ``VoiceSTT.kroko.buildinputs`` so the values
    that go into the compiler and the values that go into the build fingerprint
    can never drift apart.
    """

    env = os.environ.copy()
    existing_cmake_args = env.get("SHERPA_ONNX_CMAKE_ARGS", "").strip()
    env["SHERPA_ONNX_CMAKE_ARGS"] = (
        existing_cmake_args + " " + buildinputs.LINUX_CMAKE_FLAGS
    ).strip()
    env.setdefault("SHERPA_ONNX_MAKE_ARGS", buildinputs.LINUX_MAKE_ARGS)
    if variant == buildinputs.VARIANT_PRO:
        # Builds a Pro-capable runtime. This is a capability switch only - the
        # Pro license key is never needed at build time and is never placed
        # into the build environment.
        env[buildinputs.PRO_BUILD_ENV_NAME] = buildinputs.PRO_BUILD_ENV_VALUE
    return env


def find_linux_wheel(wheel_dir):
    """
    Finds the Kroko wheel produced by a Linux build.
    """

    wheels = sorted(
        Path(wheel_dir).glob("kroko_onnx-*.whl"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not wheels:
        raise KrokoInstallError(
            "Linux build finished, but no Kroko wheel was found in {0}.".format(wheel_dir)
        )
    return wheels[0]


def build_linux_wheel(args, repo_dir):
    """
    Builds the Kroko wheel on Linux and returns its path.
    """

    ensure_program("cmake", "CMake is required to build Kroko-ONNX from source on Linux.")
    patch_license_quiet_env(repo_dir)
    wheel_dir = repo_dir / "release_artifacts" / "linux"
    wheel_dir.mkdir(parents=True, exist_ok=True)
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--wheel-dir",
            str(wheel_dir),
        ],
        cwd=repo_dir,
        env=linux_build_env(args.variant),
    )
    return find_linux_wheel(wheel_dir)


def build_windows_wheel(args, repo_dir):
    """
    Builds the Kroko wheel on Windows and returns its path.
    """

    ensure_windows_host()
    prepare_windows_checkout(repo_dir)
    run(
        ["cmd.exe", "/c", str(repo_dir / "build_windows.bat"), "--variant", args.variant],
        cwd=repo_dir,
    )
    return find_windows_wheel(repo_dir, args.variant)


def build_wheel(args, repo_dir):
    """
    Builds the Kroko wheel for this platform and returns its path.
    """

    if os.name == "nt":
        return build_windows_wheel(args, repo_dir)
    if sys.platform.startswith("linux"):
        return build_linux_wheel(args, repo_dir)
    raise KrokoInstallError(
        "stt-install-kroko currently supports Windows and Linux. "
        "Use Kroko's upstream macOS build script on macOS."
    )


def install_linux(args, repo_dir):
    """
    Installs Kroko from source on Linux.
    """

    ensure_program("cmake", "CMake is required to build Kroko-ONNX from source on Linux.")
    patch_license_quiet_env(repo_dir)
    env = linux_build_env(args.variant)

    if args.skip_install:
        wheel_dir = repo_dir / "release_artifacts" / "linux"
        wheel_dir.mkdir(parents=True, exist_ok=True)
        run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                ".",
                "--no-deps",
                "--wheel-dir",
                str(wheel_dir),
            ],
            cwd=repo_dir,
            env=env,
        )
        return

    run([sys.executable, "-m", "pip", "install", "."], cwd=repo_dir, env=env)


def fingerprint_for(args):
    """
    Computes the build fingerprint for the requested variant.
    """

    return kroko_fingerprint.compute_fingerprint(variant=args.variant)


def artifact_store_for(args):
    """
    Opens the persistent artifact store selected for this invocation.
    """

    return kroko_artifacts.KrokoArtifactStore(getattr(args, "artifact_store", None))


def describe_artifact(args):
    """
    Reports fingerprint and artifact availability as a machine-readable dict.

    This is the read-only interface W4B and later CI use to decide whether a
    native build is needed at all. It compiles nothing and needs no checkout.
    """

    computed = fingerprint_for(args)
    store = artifact_store_for(args)
    record, problems = store.lookup(
        variant=args.variant,
        fingerprint=computed["fingerprint"],
        inputs=computed["inputs"],
    )
    payload = {
        "variant": args.variant,
        "fingerprint": computed["fingerprint"],
        "inputs": computed["inputs"],
        "artifactStore": str(store.root),
        "artifactPresent": record is not None,
    }
    if record is not None:
        payload["artifact"] = record.public_dict()
    else:
        payload["problems"] = problems
    return payload


def install_wheel(wheel_path):
    """
    Installs a built or reused Kroko wheel into this Python environment.
    """

    run([sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheel_path)])


def main(argv=None):
    """
    Runs the Kroko installer command.
    """

    args = parse_args(argv)

    if args.print_fingerprint:
        print(json.dumps(fingerprint_for(args), indent=2, sort_keys=True))
        return 0

    if args.describe_artifact:
        try:
            print(json.dumps(describe_artifact(args), indent=2, sort_keys=True))
        except kroko_artifacts.KrokoArtifactError as exc:
            print("ERROR: {0}".format(exc), file=sys.stderr)
            return 1
        return 0

    if not args.build:
        raise SystemExit("Pass --build to build and install Kroko-ONNX.")

    try:
        computed = fingerprint_for(args)
        store = artifact_store_for(args)
        print(
            "Kroko build fingerprint: {0} (variant {1}, upstream {2})".format(
                computed["fingerprint"],
                args.variant,
                buildinputs.KROKO_UPSTREAM_REVISION,
            )
        )

        # Reuse by default: a verified artifact for exactly these build inputs
        # means there is nothing to compile.
        if not args.rebuild_kroko:
            record, problems = store.lookup(
                variant=args.variant,
                fingerprint=computed["fingerprint"],
                inputs=computed["inputs"],
            )
            if record is not None:
                print("Reusing verified Kroko artifact: {0}".format(record.wheel_path))
                if not args.skip_install:
                    install_wheel(record.wheel_path)
                    _report_installed_runtime(args.variant)
                print("Kroko-ONNX is ready in this Python environment.")
                return 0
            print("No reusable Kroko artifact: {0}".format("; ".join(problems)))
        else:
            print("--rebuild-kroko: forcing a real native rebuild.")

        work_dir = preflight_build(args)
        repo_dir = prepare_checkout(args, work_dir)
        wheel = build_wheel(args, repo_dir)
        print("Built Kroko-ONNX wheel: {0}".format(wheel))

        # Verify and store before installing. A failed store leaves whatever
        # artifact was already known good untouched.
        record = store.store(
            wheel_path=wheel,
            fingerprint=computed["fingerprint"],
            inputs=computed["inputs"],
        )
        print("Stored verified Kroko artifact: {0}".format(record.wheel_path))

        if not args.skip_install:
            install_wheel(record.wheel_path)
            _report_installed_runtime(args.variant)
    except (KrokoInstallError, kroko_artifacts.KrokoArtifactError) as exc:
        print("ERROR: {0}".format(exc), file=sys.stderr)
        return 1

    print("Kroko-ONNX is ready in this Python environment.")
    return 0


def _report_installed_runtime(variant):
    """
    Verifies the installed Kroko runtime really is the requested variant.
    """

    result = kroko_artifacts.verify_installed_runtime(variant)
    if not result.get("ok"):
        raise KrokoInstallError(
            "Installed Kroko runtime failed variant verification: {0}".format(
                result.get("problem") or result.get("importError") or result
            )
        )
    print("Verified installed Kroko runtime variant: {0}".format(variant))


if __name__ == "__main__":
    raise SystemExit(main())
