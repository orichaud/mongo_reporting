# MongoDB Atlas Cluster Report Generator

Generate a report of all MongoDB Atlas clusters accessible by your API key. Lists each cluster's name, tier, type, provider, region, version, state, and disk size.

## Prerequisites

- Python 3.10+
- A MongoDB Atlas account with API access

## Installation

1. Clone the repository or download the script.

2. Create and activate a virtual environment:

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. Install dependencies:

    ```bash
    pip install -r requirements.txt
    ```

4. (Optional) Install development dependencies:

    ```bash
    pip install -r requirements-dev.txt
    ```

## Configuration

Create a `.env` file with your MongoDB Atlas API credentials:

```text
ATLAS_PUBLIC_KEY=your_public_key
ATLAS_PRIVATE_KEY=your_private_key
```

Optional environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ATLAS_ITEMS_PER_PAGE` | 500 | Items per API page (1-500) |
| `ATLAS_MAX_ATTEMPTS` | 5 | Max retries per request |
| `ATLAS_MAX_WORKERS` | 20 | Concurrent API requests |
| `ATLAS_TIMEOUT` | 30 | HTTP timeout in seconds |
| `ATLAS_HIGHLIGHT_THRESHOLD` | 30 | Highlight tiers > M{N} in red |

## Usage

```bash
python3 get_cluster_report.py [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `--max-workers N` | Concurrent API requests (default: 20) |
| `--items-per-page N` | Items per API page, 1-500 (default: 500) |
| `--max-attempts N` | Max retries per request (default: 5) |
| `--timeout N` | HTTP timeout in seconds (default: 30) |
| `--highlight-threshold N` | Highlight tiers > M{N} in red (default: 30) |
| `--no-color` | Disable colored output |
| `--force-color` | Force colored output (ignore TTY detection) |
| `-q, --quiet` | Suppress progress messages |
| `--sort-by COLUMN` | Sort by: project, cluster, tier, disk, provider, region |
| `--project PATTERN` | Include projects matching glob pattern (repeatable) |
| `--exclude-project PATTERN` | Exclude projects matching glob pattern (repeatable) |
| `--output FILE` | Export report to file (format inferred from extension) |
| `--output-format FORMAT` | Force output format: csv or json |

### Examples

```bash
# Report all clusters
python3 get_cluster_report.py

# Only production projects
python3 get_cluster_report.py --project "prod-*"

# Exclude tools projects
python3 get_cluster_report.py --exclude-project "*-tools"

# Combine include and exclude
python3 get_cluster_report.py --project "prod-*" --exclude-project "*-tools"

# Sort by disk size (largest first)
python3 get_cluster_report.py --sort-by disk

# Export to CSV
python3 get_cluster_report.py --output report.csv

# Quiet mode with JSON export
python3 get_cluster_report.py -q --output report.json

# Multiple project patterns
python3 get_cluster_report.py --project "prod-*" --project "uat-*"
```

## Output

The script outputs:
1. A formatted table with cluster details
2. Summary statistics (total projects, clusters, disk, breakdown by tier/provider/type)
3. Execution metrics

Clusters with instance size larger than the highlight threshold (default: M30) are shown in red.

## Running Tests

```bash
PYTHONPATH=. python3 -m pytest -v
```

## How it Works

1. Fetches all projects accessible by the API key
2. Filters projects based on include/exclude patterns
3. Concurrently fetches clusters for each project
4. Displays formatted report with sorting and highlighting
5. Optionally exports to CSV or JSON
