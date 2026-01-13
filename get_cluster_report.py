"""MongoDB Atlas Cluster Report Generator."""

import argparse
import concurrent.futures
import csv
import fnmatch
import json
import logging
import os
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.auth import HTTPDigestAuth

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)
__version__ = "0.1.0"


@dataclass
class Config:
    items_per_page: int = 500
    max_attempts: int = 5
    max_workers: int = 20
    timeout: int = 30
    highlight_threshold: int = 30
    no_color: bool = False
    force_color: bool = False
    quiet: bool = False
    sort_by: str = "project"
    include_projects: list[str] = field(default_factory=list)
    exclude_projects: list[str] = field(default_factory=list)

    def color(self, code: str) -> str:
        if self.force_color or (not self.no_color and sys.stdout.isatty()):
            return code
        return ""


load_dotenv()
config = Config(
    items_per_page=int(os.getenv("ATLAS_ITEMS_PER_PAGE", "500")),
    max_attempts=int(os.getenv("ATLAS_MAX_ATTEMPTS", "5")),
    max_workers=int(os.getenv("ATLAS_MAX_WORKERS", "20")),
    timeout=int(os.getenv("ATLAS_TIMEOUT", "30")),
    highlight_threshold=int(os.getenv("ATLAS_HIGHLIGHT_THRESHOLD", "30")),
)

ATLAS_PUBLIC_KEY = os.getenv("ATLAS_PUBLIC_KEY")
ATLAS_PRIVATE_KEY = os.getenv("ATLAS_PRIVATE_KEY")
API_BASE = "https://cloud.mongodb.com/api/atlas/v1.0"
_session: requests.Session | None = None


def get_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.auth = HTTPDigestAuth(ATLAS_PUBLIC_KEY, ATLAS_PRIVATE_KEY)
        _session.mount(
            "https://",
            requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20),
        )
    return _session


def api_get(endpoint: str, params: dict | None = None) -> dict | None:
    """GET request to Atlas API with retry."""
    backoff = 1
    for attempt in range(config.max_attempts):
        try:
            r = get_session().get(
                f"{API_BASE}{endpoint}", params=params, timeout=config.timeout
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response else None
            if (
                status in {429, 500, 502, 503, 504}
                and attempt < config.max_attempts - 1
            ):
                retry = e.response.headers.get("Retry-After", "")
                wait = max(backoff, int(retry) if retry.isdigit() else 0)
                logger.warning("HTTP %s; retry in %.1fs...", status, wait)
                time.sleep(wait)
                backoff *= 2
                continue
            logger.error("HTTP Error: %s", e)
            if e.response is not None:
                logger.error("Response: %s", e.response.text)
            return None
        except requests.exceptions.RequestException as e:
            if attempt < config.max_attempts - 1:
                logger.warning("Request error: %s. Retry in %ss...", e, backoff)
                time.sleep(backoff)
                backoff *= 2
                continue
            logger.error("Request Error: %s", e)
            return None
    return None


def api_get_all(endpoint: str, params: dict | None = None) -> list[dict]:
    """Fetch all pages from paginated endpoint."""
    results, page = [], 1
    base = params.copy() if params else {}
    while True:
        data = api_get(
            endpoint, {**base, "pageNum": page, "itemsPerPage": config.items_per_page}
        )
        if not data or "results" not in data:
            break
        results.extend(data["results"])
        if (
            not data["results"]
            or len(results) >= data.get("totalCount", 0)
            or len(data["results"]) < config.items_per_page
        ):
            break
        page += 1
    return results


def filter_projects(projects: list[dict]) -> list[dict]:
    if not config.include_projects and not config.exclude_projects:
        return projects

    def match(name: str, patterns: list[str]) -> bool:
        return any(fnmatch.fnmatch(name.lower(), p.lower()) for p in patterns)

    return [
        p
        for p in projects
        if (
            not config.include_projects
            or match(p.get("name", ""), config.include_projects)
        )
        and not (
            config.exclude_projects
            and match(p.get("name", ""), config.exclude_projects)
        )
    ]


def get_tier(c: dict) -> str:
    if c.get("clusterType") == "SERVERLESS":
        return "Serverless"
    return c.get("providerSettings", {}).get("instanceSizeName", "N/A")


def is_large_tier(tier: str) -> bool:
    m = re.match(r"M(\d+)", tier)
    return m is not None and int(m.group(1)) > config.highlight_threshold


def parse_args():
    p = argparse.ArgumentParser(
        description="Generate a report of all MongoDB Atlas clusters.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                              # Report all clusters
  %(prog)s --project "prod-*"           # Only production projects
  %(prog)s --exclude-project "*-tools"  # Exclude tools projects
  %(prog)s --sort-by disk               # Sort by disk size (largest first)
  %(prog)s --output report.csv          # Export to CSV
  %(prog)s -q --output-format json | jq # JSON to stdout, pipe to jq
""",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    p.add_argument(
        "--max-workers",
        type=int,
        default=config.max_workers,
        help=f"concurrent API requests (default: {config.max_workers})",
    )
    p.add_argument(
        "--items-per-page",
        type=int,
        default=config.items_per_page,
        help=f"items per API page, 1-500 (default: {config.items_per_page})",
    )
    p.add_argument(
        "--max-attempts",
        type=int,
        default=config.max_attempts,
        help=f"max retries per request (default: {config.max_attempts})",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=config.timeout,
        help=f"HTTP timeout in seconds (default: {config.timeout})",
    )
    p.add_argument(
        "--highlight-threshold",
        type=int,
        default=config.highlight_threshold,
        help=f"highlight tiers larger than M{{N}} in red (default: {config.highlight_threshold})",
    )
    p.add_argument("--no-color", action="store_true", help="disable colored output")
    p.add_argument(
        "--force-color", action="store_true", help="force colored output (ignore TTY)"
    )
    p.add_argument(
        "-q", "--quiet", action="store_true", help="suppress progress messages"
    )
    p.add_argument(
        "--sort-by",
        choices=["project", "cluster", "tier", "disk", "provider", "region"],
        default="project",
        help="sort output by column (default: project)",
    )
    p.add_argument(
        "--project",
        action="append",
        default=[],
        metavar="PATTERN",
        help="include projects matching glob pattern (repeatable)",
    )
    p.add_argument(
        "--exclude-project",
        action="append",
        default=[],
        metavar="PATTERN",
        help="exclude projects matching glob pattern (repeatable)",
    )
    p.add_argument(
        "--output",
        type=str,
        metavar="FILE",
        help="export report to file (format inferred from extension)",
    )
    p.add_argument(
        "--output-format",
        choices=["csv", "json"],
        help="output format; json without --output prints to stdout for piping",
    )
    return p.parse_args()


def validate_args(args):
    errs = []
    if not 1 <= args.items_per_page <= 500:
        errs.append("--items-per-page must be 1-500")
    for name, val, min_val in [
        ("max-attempts", args.max_attempts, 1),
        ("max-workers", args.max_workers, 1),
        ("timeout", args.timeout, 1),
    ]:
        if val < min_val:
            errs.append(f"--{name} must be >= {min_val}")
    if args.highlight_threshold < 0:
        errs.append("--highlight-threshold must be >= 0")
    if errs:
        for e in errs:
            print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def infer_format(path: Path, explicit: str | None) -> str:
    if explicit:
        return explicit
    fmt = {".json": "json", ".csv": "csv"}.get(path.suffix.lower())
    if not fmt:
        raise ValueError("Cannot infer format. Use --output-format.")
    return fmt


def export_report(reports: list[dict], path: Path, fmt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).isoformat()
    sorted_reps = sorted(reports, key=lambda x: x["project_name"])

    if fmt == "json":
        path.write_text(
            json.dumps({"generated_at": ts, "projects": sorted_reps}, indent=2),
            encoding="utf-8",
        )
        logger.info("Exported to %s (JSON)", path)
        return

    fields = [
        "generated_at",
        "project_name",
        "cluster_name",
        "tier",
        "cluster_type",
        "provider",
        "region",
        "version",
        "state",
        "pit",
        "disk_size_gb",
    ]
    rows = []
    for r in sorted_reps:
        if not r.get("clusters"):
            rows.append(
                {
                    f: (
                        ts
                        if f == "generated_at"
                        else r["project_name"] if f == "project_name" else ""
                    )
                    for f in fields
                }
            )
        else:
            for c in r["clusters"]:
                ps = c.get("providerSettings", {})
                rows.append(
                    {
                        "generated_at": ts,
                        "project_name": r["project_name"],
                        "cluster_name": c.get("name", ""),
                        "tier": get_tier(c),
                        "cluster_type": c.get("clusterType", ""),
                        "provider": ps.get("providerName", "N/A"),
                        "region": ps.get("regionName", "N/A"),
                        "version": c.get("mongoDBMajorVersion", "N/A"),
                        "state": c.get("stateName", "N/A"),
                        "pit": "Yes" if c.get("pitEnabled") else "No",
                        "disk_size_gb": c.get("diskSizeGB", 0.0),
                    }
                )
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    logger.info("Exported to %s (CSV)", path)


def print_report(reports: list[dict]) -> None:
    red, reset = config.color("\x1b[91m"), config.color("\x1b[0m")
    hdrs = [
        "Project",
        "Cluster",
        "Tier",
        "Type",
        "Provider",
        "Region",
        "Ver",
        "State",
        "PIT",
        "Disk GB",
    ]
    rows = []
    for r in sorted(reports, key=lambda x: x["project_name"]):
        if not r.get("clusters"):
            rows.append(([r["project_name"], "No clusters"] + [""] * 8, False))
        else:
            for c in r["clusters"]:
                t, ps = get_tier(c), c.get("providerSettings", {})
                rows.append(
                    (
                        [
                            r["project_name"],
                            c.get("name", ""),
                            t,
                            c.get("clusterType", ""),
                            ps.get("providerName", "N/A"),
                            ps.get("regionName", "N/A"),
                            c.get("mongoDBMajorVersion", "N/A"),
                            c.get("stateName", "N/A"),
                            "Yes" if c.get("pitEnabled") else "No",
                            f"{c.get('diskSizeGB', 0.0):.1f}",
                        ],
                        is_large_tier(t),
                    )
                )

    # Sort
    idx = {
        "project": 0,
        "cluster": 1,
        "tier": 2,
        "provider": 4,
        "region": 5,
        "disk": 9,
    }.get(config.sort_by, 0)

    def skey(row):
        v = row[0][idx]
        if idx == 9:
            return (float(v or 0),)
        if idx == 2:
            m = re.match(r"M(\d+)", v)
            return (int(m.group(1)) if m else 0,)
        return (v.lower(),)

    rows.sort(key=skey, reverse=(config.sort_by == "disk"))

    widths = [max(len(h), *(len(r[0][i]) for r in rows)) for i, h in enumerate(hdrs)]
    sep, w = " | ", sum(widths) + 3 * (len(widths) - 1)

    def fmt(v):
        return sep.join(f"{v[i]:<{widths[i]}}" for i in range(len(v)))

    print("\n" + "=" * w)
    print(fmt(hdrs))
    print("-" * w)
    for vals, hl in rows:
        ln = fmt(vals)
        print(f"{red}{ln}{reset}" if hl else ln)
    print("=" * w)


def print_summary(reports: list[dict]) -> None:
    clusters = [c for r in reports for c in r.get("clusters", [])]
    tiers = Counter(get_tier(c) for c in clusters)
    provs = Counter(
        c.get("providerSettings", {}).get("providerName", "N/A") for c in clusters
    )
    types = Counter(c.get("clusterType", "N/A") for c in clusters)
    disk = sum(c.get("diskSizeGB", 0.0) for c in clusters)
    print(
        f"\n📈 Summary:\n   Projects: {len(reports)}  |  Clusters: {len(clusters)}  |  Disk: {disk:,.1f} GB"
    )
    if tiers:
        print(f"   Tiers: {', '.join(f'{k}:{v}' for k, v in tiers.most_common())}")
    if provs:
        print(f"   Providers: {', '.join(f'{k}:{v}' for k, v in provs.most_common())}")
    if types:
        print(f"   Types: {', '.join(f'{k}:{v}' for k, v in types.most_common())}")


def main() -> None:
    global config
    t0 = time.perf_counter()
    args = parse_args()
    validate_args(args)

    # Apply args to config
    for k in [
        "items_per_page",
        "max_attempts",
        "max_workers",
        "timeout",
        "highlight_threshold",
        "no_color",
        "force_color",
        "quiet",
        "sort_by",
    ]:
        setattr(config, k, getattr(args, k.replace("-", "_")))
    config.include_projects, config.exclude_projects = (
        args.project,
        args.exclude_project,
    )
    if config.quiet:
        logger.setLevel(logging.WARNING)

    if not ATLAS_PUBLIC_KEY or not ATLAS_PRIVATE_KEY:
        logger.error("FATAL: Set ATLAS_PUBLIC_KEY and ATLAS_PRIVATE_KEY in .env")
        sys.exit(1)

    # Fetch projects
    t1 = time.perf_counter()
    logger.info("Fetching projects...")
    projects = api_get_all("/groups")
    if not projects:
        logger.error("No projects found.")
        sys.exit(1)
    logger.info("Found %d projects.", len(projects))
    projects = filter_projects(projects)
    if not projects:
        logger.error("No projects match filters.")
        sys.exit(1)
    if config.include_projects or config.exclude_projects:
        logger.info("After filtering: %d projects.", len(projects))
    proj_time = time.perf_counter() - t1

    # Fetch clusters
    t2 = time.perf_counter()
    reports = []
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=min(config.max_workers, len(projects))
    ) as ex:
        futs = {
            ex.submit(
                lambda p: {
                    "project_name": p["name"],
                    "clusters": api_get_all(f"/groups/{p['id']}/clusters"),
                },
                p,
            ): p
            for p in projects
        }
        for f in concurrent.futures.as_completed(futs):
            try:
                reports.append(f.result())
            except Exception as e:
                logger.error("Failed '%s': %s", futs[f].get("name"), e)
    clust_time = time.perf_counter() - t2
    total_clusters = sum(len(r.get("clusters", [])) for r in reports)

    # JSON to stdout (for piping to jq)
    if args.output_format == "json" and not args.output:
        ts = datetime.now(timezone.utc).isoformat()
        sorted_reps = sorted(reports, key=lambda x: x["project_name"])
        print(json.dumps({"generated_at": ts, "projects": sorted_reps}, indent=2))
        return

    print_report(reports)
    print_summary(reports)

    exp_time = 0.0
    if args.output:
        t3 = time.perf_counter()
        path = Path(args.output).expanduser().resolve()
        try:
            export_report(reports, path, infer_format(path, args.output_format))
        except ValueError as e:
            logger.error("Output error: %s", e)
            sys.exit(1)
        exp_time = time.perf_counter() - t3

    total = time.perf_counter() - t0
    tstr = (
        f"{total*1000:.0f}ms"
        if total < 1
        else f"{total:.1f}s" if total < 60 else f"{int(total//60)}m{total%60:.1f}s"
    )
    print(
        f"\n📊 Metrics: projects {proj_time:.2f}s | clusters {clust_time:.2f}s ({total_clusters})"
        + (f" | export {exp_time:.2f}s" if exp_time else "")
        + f" | total {tstr}"
    )


if __name__ == "__main__":
    main()
