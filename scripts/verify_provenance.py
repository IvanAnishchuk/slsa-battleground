"""Verify SLSA provenance across all distribution points.

Downloads artifacts from GitHub Releases and PyPI, verifies attestations,
sigstore signatures, and SHA256 checksums, and prints provenance details.
Also checks local dist/ if present.

Usage:
    uv run python scripts/verify_provenance.py [VERSION]
    uv run python scripts/verify_provenance.py 0.0.1
    uv run python scripts/verify_provenance.py          # auto-detects from __init__.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_OWNER = "IvanAnishchuk"
REPO_NAME = "slsa-battleground"
REPO_SLUG = f"{REPO_OWNER}/{REPO_NAME}"
PACKAGE_NAME = "slsa-battleground"
DIST_EXTENSIONS = (".whl", ".tar.gz")


def get_version() -> str:
    if len(sys.argv) > 1:
        return sys.argv[1].removeprefix("v")
    init = REPO_ROOT / "src" / "slsa_battleground" / "__init__.py"
    for line in init.read_text().splitlines():
        if line.startswith("__version__"):
            return line.split('"')[1]
    console.print("[red]Could not detect version. Pass it as an argument.[/]")
    sys.exit(1)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        cmd,
        capture_output=True,
        text=True,
        check=False,
        **kwargs,
    )


def is_dist_file(name: str) -> bool:
    return any(name.endswith(ext) for ext in DIST_EXTENSIONS)


def header(title: str) -> None:
    console.print()
    console.rule(f"[bold blue]{title}[/]")
    console.print()


def ok(msg: str) -> None:
    console.print(f"  [bold green]OK[/] {msg}")


def fail(msg: str) -> None:
    console.print(f"  [bold red]FAIL[/] {msg}")


def info(msg: str) -> None:
    console.print(f"  [dim]{msg}[/]")


# ── Collectors ────────────────────────────────────────────────────


def collect_local(version: str) -> dict[str, Path]:
    """Find matching artifacts in local dist/."""
    dist_dir = REPO_ROOT / "dist"
    if not dist_dir.is_dir():
        return {}
    found = {}
    for f in sorted(dist_dir.iterdir()):
        if is_dist_file(f.name) and version in f.name:
            found[f.name] = f
    return found


def download_github_release(version: str, dest: Path) -> dict[str, Path]:
    """Download release artifacts from GitHub."""
    tag = f"v{version}"
    result = run(["gh", "release", "download", tag, "--repo", REPO_SLUG, "--dir", str(dest)])
    if result.returncode != 0:
        console.print(f"  [yellow]GitHub Release {tag} not found or download failed[/]")
        if result.stderr:
            info(result.stderr.strip())
        return {}
    found = {}
    for f in sorted(dest.iterdir()):
        if is_dist_file(f.name):
            found[f.name] = f
    return found


def download_pypi(version: str, dest: Path) -> dict[str, Path]:
    """Download package from PyPI."""
    result = run(
        [
            "pip",
            "download",
            "--no-deps",
            "--dest",
            str(dest),
            f"{PACKAGE_NAME}=={version}",
        ]
    )
    if result.returncode != 0:
        console.print(f"  [yellow]PyPI download failed for {PACKAGE_NAME}=={version}[/]")
        if result.stderr:
            info(result.stderr.strip())
        return {}
    # Also try sdist
    run(
        [
            "pip",
            "download",
            "--no-deps",
            "--no-binary",
            ":all:",
            "--dest",
            str(dest),
            f"{PACKAGE_NAME}=={version}",
        ]
    )
    found = {}
    for f in sorted(dest.iterdir()):
        if is_dist_file(f.name):
            found[f.name] = f
    return found


# ── Verification ──────────────────────────────────────────────────


def verify_checksums(artifacts: dict[str, Path], sums_file: Path | None) -> bool:
    """Verify SHA256SUMS.txt if present, print hashes either way."""
    expected: dict[str, str] = {}
    if sums_file and sums_file.exists():
        for line in sums_file.read_text().splitlines():
            if line.strip():
                h, name = line.split(None, 1)
                expected[name.strip()] = h.strip()

    all_ok = True
    for name, path in sorted(artifacts.items()):
        actual = sha256(path)
        if name in expected:
            if actual == expected[name]:
                ok(f"{name}: {actual}")
            else:
                fail(f"{name}: expected {expected[name]}, got {actual}")
                all_ok = False
        else:
            info(f"{name}: {actual}")
    return all_ok


def verify_gh_attestation(path: Path) -> dict | None:
    """Run gh attestation verify and return parsed provenance."""
    result = run(
        [
            "gh",
            "attestation",
            "verify",
            str(path),
            "--repo",
            REPO_SLUG,
            "--format",
            "json",
        ]
    )
    if result.returncode != 0:
        fail(f"gh attestation verify: {result.stderr.strip()}")
        return None
    ok(f"gh attestation verify: {path.name}")
    try:
        records = json.loads(result.stdout)
        if isinstance(records, list) and records:
            return records[0]
    except json.JSONDecodeError:
        pass
    return None


def verify_sigstore(path: Path, bundle: Path | None) -> bool:
    """Verify sigstore signature if bundle is available."""
    if not bundle or not bundle.exists():
        info(f"sigstore: no bundle for {path.name}")
        return True  # not a failure, just not available

    result = run(
        [
            "uv",
            "tool",
            "run",
            "sigstore",
            "verify",
            "identity",
            "--cert-identity-regexp",
            f"^https://github\\.com/{REPO_OWNER}/{REPO_NAME}/\\.github/workflows/release\\.yml@",
            "--cert-oidc-issuer",
            "https://token.actions.githubusercontent.com",
            "--bundle",
            str(bundle),
            str(path),
        ]
    )
    if result.returncode != 0:
        fail(f"sigstore verify: {result.stderr.strip()}")
        return False
    ok(f"sigstore verify: {path.name}")
    return True


def print_provenance_details(attestation: dict) -> None:
    """Extract and print human-readable provenance from attestation JSON."""
    vr = attestation.get("verificationResult", {})
    cert = vr.get("signature", {}).get("certificate", {})
    stmt = vr.get("statement", {})
    predicate = stmt.get("predicate", {})
    build_def = predicate.get("buildDefinition", {})
    run_details = predicate.get("runDetails", {})
    ext_params = build_def.get("externalParameters", {})
    workflow = ext_params.get("workflow", {})
    resolved = build_def.get("resolvedDependencies", [])
    timestamps = vr.get("verifiedTimestamps", [])

    table = Table(title="Provenance Details", show_header=False, padding=(0, 2), expand=True)
    table.add_column("Field", style="bold cyan", min_width=24, max_width=30)
    table.add_column("Value", overflow="fold")

    table.add_row("Predicate type", stmt.get("predicateType", "?"))
    table.add_row("Build type", build_def.get("buildType", "?"))
    table.add_row("Workflow", workflow.get("path", "?"))
    table.add_row("Workflow ref", workflow.get("ref", "?"))
    table.add_row("Source repo", workflow.get("repository", "?"))

    if resolved:
        dep = resolved[0]
        table.add_row("Source URI", dep.get("uri", "?"))
        commit = dep.get("digest", {}).get("gitCommit", "?")
        table.add_row("Source commit", commit)

    table.add_row("Builder ID", run_details.get("builder", {}).get("id", "?"))
    table.add_row("Invocation", run_details.get("metadata", {}).get("invocationId", "?"))

    github = build_def.get("internalParameters", {}).get("github", {})
    table.add_row("Event", github.get("event_name", "?"))
    table.add_row("Runner", github.get("runner_environment", "?"))

    # Certificate details
    table.add_row("", "")
    table.add_row("[bold]Certificate[/]", "")
    table.add_row("Issuer", cert.get("certificateIssuer", "?"))
    table.add_row("OIDC issuer", cert.get("issuer", "?"))
    table.add_row("SAN", cert.get("subjectAlternativeName", "?"))
    table.add_row("Trigger", cert.get("githubWorkflowTrigger", "?"))
    table.add_row("Visibility", cert.get("sourceRepositoryVisibilityAtSigning", "?"))

    if timestamps:
        ts = timestamps[0]
        table.add_row("", "")
        table.add_row("[bold]Transparency log[/]", "")
        table.add_row("Log type", ts.get("type", "?"))
        table.add_row("Log URI", ts.get("uri", "?"))
        table.add_row("Timestamp", ts.get("timestamp", "?"))

    # Subjects
    subjects = stmt.get("subject", [])
    if subjects:
        table.add_row("", "")
        table.add_row("[bold]Attested subjects[/]", "")
        for subj in subjects:
            digest = subj.get("digest", {}).get("sha256", "?")
            table.add_row(subj.get("name", "?"), f"sha256:{digest}")

    console.print()
    console.print(table)


# ── Cross-source comparison ───────────────────────────────────────


def compare_hashes(sources: dict[str, dict[str, str]]) -> bool:
    """Compare artifact hashes across distribution sources."""
    all_names: set[str] = set()
    for hashes in sources.values():
        all_names.update(hashes)

    all_match = True
    table = Table(title="Cross-source Hash Comparison", expand=True)
    table.add_column("Artifact", style="bold", overflow="fold")
    for source in sources:
        table.add_column(source)

    for name in sorted(all_names):
        row = [name]
        values = set()
        for source in sources:
            h = sources[source].get(name, "")
            row.append(h[:16] + "..." if h else "[dim]n/a[/]")
            if h:
                values.add(h)
        if len(values) > 1:
            all_match = False
            row[0] = f"[red]{name}[/]"
        table.add_row(*row)

    console.print()
    console.print(table)
    if all_match:
        ok("All hashes match across sources")
    else:
        fail("Hash mismatch detected between sources!")
    return all_match


# ── Main ──────────────────────────────────────────────────────────


def main() -> int:
    version = get_version()
    console.print(Panel(f"Verifying provenance for [bold]{PACKAGE_NAME} {version}[/]"))

    failures = 0
    source_hashes: dict[str, dict[str, str]] = {}

    # ── Local dist/ ───────────────────────────────────────────
    header("Local dist/")
    local = collect_local(version)
    if local:
        console.print(f"  Found {len(local)} artifact(s)")
        local_sums = REPO_ROOT / "dist" / "SHA256SUMS.txt"
        verify_checksums(local, local_sums if local_sums.exists() else None)
        source_hashes["local"] = {n: sha256(p) for n, p in local.items()}
        for _name, path in local.items():
            bundle = path.parent / f"{path.name}.sigstore.json"
            verify_sigstore(path, bundle)
    else:
        info("No local artifacts found in dist/")

    with tempfile.TemporaryDirectory(prefix="verify-") as tmpdir:
        tmp = Path(tmpdir)

        # ── GitHub Release ────────────────────────────────────
        header("GitHub Release")
        gh_dir = tmp / "github"
        gh_dir.mkdir()
        gh_artifacts = download_github_release(version, gh_dir)
        if gh_artifacts:
            console.print(f"  Found {len(gh_artifacts)} artifact(s)")
            gh_sums = gh_dir / "SHA256SUMS.txt"
            verify_checksums(gh_artifacts, gh_sums)
            source_hashes["github"] = {n: sha256(p) for n, p in gh_artifacts.items()}
            attestation_shown = False
            for _name, path in gh_artifacts.items():
                att = verify_gh_attestation(path)
                if att and not attestation_shown:
                    print_provenance_details(att)
                    attestation_shown = True
                bundle = gh_dir / f"{path.name}.sigstore.json"
                verify_sigstore(path, bundle)
        else:
            info("No GitHub Release artifacts available")

        # ── PyPI ──────────────────────────────────────────────
        header("PyPI")
        pypi_dir = tmp / "pypi"
        pypi_dir.mkdir()
        pypi_artifacts = download_pypi(version, pypi_dir)
        if pypi_artifacts:
            console.print(f"  Found {len(pypi_artifacts)} artifact(s)")
            source_hashes["pypi"] = {n: sha256(p) for n, p in pypi_artifacts.items()}
            for name in sorted(pypi_artifacts):
                h = source_hashes["pypi"][name]
                info(f"{name}: {h}")
            for _name, path in pypi_artifacts.items():
                verify_gh_attestation(path)
        else:
            info("No PyPI artifacts available")

    # ── Cross-source comparison ───────────────────────────────
    if len(source_hashes) > 1:
        header("Cross-source Comparison")
        if not compare_hashes(source_hashes):
            failures += 1

    # ── Summary ───────────────────────────────────────────────
    console.print()
    if failures:
        console.print(Panel("[bold red]Verification completed with failures[/]"))
        return 1
    console.print(Panel("[bold green]All verifications passed[/]"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
