import os
import platform
import shutil
import subprocess
from pathlib import Path

from ..ui import step_header, success, info
from src.app.intelligence.paths import server_dir as _server_dir

LLAMA_CPP_REF = "81bc6b83f827df746eb129235488d325c49cae52"
_LLAMA_CPP_REPO = "https://github.com/ggerganov/llama.cpp.git"

BINARY_NAME = "llama-server.exe" if platform.system() == "Windows" else "llama-server"

_CMAKE_CONFIGURE_FLAGS = [
    "-DCMAKE_BUILD_TYPE=Release",
    "-DGGML_NATIVE=ON",
    "-DBUILD_SHARED_LIBS=OFF",
    "-DLLAMA_CURL=OFF",
]


def _verify_binary_runs(binary_path: Path) -> None:
    try:
        subprocess.run([str(binary_path), "--help"], capture_output=True, timeout=10, check=True)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(
            f"Compiled llama-server binary at {binary_path} could not run ({exc}). "
            "Delete the server directory under your data dir and re-run `tollgate init` "
            "to rebuild it."
        ) from exc


def _require_build_tools() -> None:
    has_compiler = shutil.which("gcc") or shutil.which("clang") or shutil.which("cc")
    missing = [tool for tool in ("git", "cmake") if shutil.which(tool) is None]
    if not has_compiler:
        missing.append("a C/C++ compiler (gcc/clang)")

    if missing:
        raise RuntimeError(
            "Missing build tools required to compile llama-server: " + ", ".join(missing) + ". "
            "The Tollgate Docker image already provides these - if you're running `tollgate init` "
            "outside Docker, install a C++ toolchain (build-essential-equivalent), cmake, and git first."
        )


def _clone_and_checkout(src_dir: Path) -> None:
    subprocess.run(
        ["git", "clone", "--filter=blob:none", _LLAMA_CPP_REPO, str(src_dir)],
        check=True,
    )
    subprocess.run(["git", "-C", str(src_dir), "fetch", "--depth", "1", "origin", LLAMA_CPP_REF], check=True)
    subprocess.run(["git", "-C", str(src_dir), "checkout", LLAMA_CPP_REF], check=True)


def run(config: dict) -> dict:
    step_header(2, "Routing Intelligence Server", total=8)

    server_dir = _server_dir()
    binary_path = server_dir / BINARY_NAME

    if binary_path.exists():
        _verify_binary_runs(binary_path)
        success(f"llama-server already present at [dim]{binary_path}[/dim]")
        return config

    _require_build_tools()
    server_dir.mkdir(parents=True, exist_ok=True)

    build_root = server_dir / "_build"
    src_dir = build_root / "llama.cpp"

    if not src_dir.exists():
        info("Cloning llama.cpp — this runs once")
        _clone_and_checkout(src_dir)

    info("Compiling llama-server for this machine — this runs once and can take several minutes")

    configure_flags = list(_CMAKE_CONFIGURE_FLAGS)
    if platform.system() == "Darwin":
        configure_flags.append("-DGGML_METAL=ON")

    subprocess.run(["cmake", "-B", "build", *configure_flags], cwd=src_dir, check=True)

    jobs = min(os.cpu_count() or 2, 8)
    subprocess.run(
        ["cmake", "--build", "build", "--config", "Release", "--target", "llama-server", "-j", str(jobs)],
        cwd=src_dir,
        check=True,
    )

    built_binary = src_dir / "build" / "bin" / BINARY_NAME
    shutil.copy2(built_binary, binary_path)
    binary_path.chmod(binary_path.stat().st_mode | 0o111)

    shutil.rmtree(build_root, ignore_errors=True)

    _verify_binary_runs(binary_path)

    success(f"llama-server compiled and saved to [dim]{server_dir}[/dim]")
    return config
