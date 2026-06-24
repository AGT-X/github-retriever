#Github Retriever

import os
import subprocess
import tkinter as tk
from tkinter import messagebox, filedialog
import csv
import difflib
from datetime import datetime, timezone
import hashlib

import requests

downloaded_files = []


APP_NAME = "GitHub Script Retriever"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Alfredo Tapia"

def run_gh_command(args):
    try:
        result = subprocess.run(
            ["gh"] + args,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except FileNotFoundError:
        raise RuntimeError(
            "GitHub CLI is not installed or not available in PATH. "
            "Install GitHub CLI and run: gh auth login"
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e.stderr.strip() or "GitHub CLI command failed.")


def get_github_token():
    return run_gh_command(["auth", "token"])


def confirm_authenticated():
    try:
        run_gh_command(["auth", "status"])
        return True
    except RuntimeError:
        return False

def retrieve_file(repo, branch, file_path, token):
    url = f"https://api.github.com/repos/{repo}/contents/{file_path}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    params = {
        "ref": branch
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code == 404:
        raise RuntimeError("File not found, branch not found, or you do not have access.")

    if response.status_code >= 400:
        raise RuntimeError(f"GitHub API error: {response.status_code} - {response.text}")

    return response.text

def get_last_modified_info(repo, branch, file_path, token):
    url = f"https://api.github.com/repos/{repo}/commits"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    params = {
        "sha": branch,
        "path": file_path,
        "per_page": 1
    }

    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code >= 400:
        raise RuntimeError(
            f"Could not retrieve last modified information: "
            f"{response.status_code} - {response.text}"
        )

    commits = response.json()

    if not commits:
        return {
            "date": "Unknown",
            "author": "Unknown",
            "message": "No commit history found for this file",
            "sha": "Unknown",
            "url": ""
        }

    latest_commit = commits[0]
    commit = latest_commit.get("commit", {})

    author_info = commit.get("author", {}) or {}
    date = author_info.get("date", "Unknown")
    author = author_info.get("name", "Unknown")
    message = commit.get("message", "").split("\n")[0]
    sha = latest_commit.get("sha", "Unknown")
    html_url = latest_commit.get("html_url", "")

    return {
        "date": date,
        "author": author,
        "message": message,
        "sha": sha,
        "url": html_url
    }

def normalize_script_path(script_name, repo, branch):
    """
    Cleans up script paths pasted by the user.

    Supports:
    - scripts/my_script.py
    - scripts\\my_script.py
    - /scripts/my_script.py
    - "scripts/my_script.py"
    - https://github.com/org/repo/blob/main/scripts/my_script.py
    """

    cleaned = script_name.strip().strip('"').strip("'")
    cleaned = cleaned.replace("\\", "/")

    github_blob_prefix = f"https://github.com/{repo}/blob/{branch}/"

    if cleaned.startswith(github_blob_prefix):
        cleaned = cleaned.replace(github_blob_prefix, "", 1)

    if cleaned.startswith("/"):
        cleaned = cleaned[1:]

    return cleaned


def parse_script_line(line, default_repo, default_branch):
    """
    Supports these formats:

    path/to/script.py
    org/repo | branch | path/to/script.py
    org/repo, branch, path/to/script.py
    """

    cleaned = line.strip()

    if not cleaned:
        return None

    if "|" in cleaned:
        parts = [part.strip() for part in cleaned.split("|")]
    elif "," in cleaned:
        parts = [part.strip() for part in cleaned.split(",", 2)]
    else:
        parts = [cleaned]

    if len(parts) == 1:
        return {
            "repo": default_repo,
            "branch": default_branch,
            "script_name": parts[0]
        }

    if len(parts) == 3:
        return {
            "repo": parts[0],
            "branch": parts[1],
            "script_name": parts[2]
        }

    raise RuntimeError(
        f"Invalid script list entry:\n\n{line}\n\n"
        "Use either:\n"
        "path/to/script.py\n"
        "or\n"
        "org/repo | branch | path/to/script.py"
    )


def resolve_file_path(repo, branch, script_name, token):
    """
    Resolves a script name or path against the GitHub repo tree.

    Supports:
    - exact full path
    - full path with wrong capitalization
    - filename only
    """

    script_name = normalize_script_path(script_name, repo, branch)

    url = f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json"
    }

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code == 404:
        raise RuntimeError(f"Repository or branch not found, or you do not have access: {repo} / {branch}")

    if response.status_code >= 400:
        raise RuntimeError(f"GitHub API error for {repo}: {response.status_code} - {response.text}")

    data = response.json()
    tree = data.get("tree", [])

    exact_matches = [
        item["path"]
        for item in tree
        if item.get("type") == "blob"
        and item["path"] == script_name
    ]

    if len(exact_matches) == 1:
        return exact_matches[0]

    path_matches = [
        item["path"]
        for item in tree
        if item.get("type") == "blob"
        and item["path"].lower() == script_name.lower()
    ]

    if len(path_matches) == 1:
        return path_matches[0]

    if len(path_matches) > 1:
        match_list = "\n".join(path_matches[:20])
        raise RuntimeError(
            f"Multiple files matched this path in {repo}:\n\n{match_list}"
        )

    filename_matches = [
        item["path"]
        for item in tree
        if item.get("type") == "blob"
        and os.path.basename(item["path"]).lower() == os.path.basename(script_name).lower()
    ]

    if len(filename_matches) == 1:
        return filename_matches[0]

    if len(filename_matches) > 1:
        match_list = "\n".join(filename_matches[:20])
        raise RuntimeError(
            f"Multiple files matched '{script_name}' in {repo}. "
            f"Please enter the full path exactly:\n\n{match_list}"
        )

    raise RuntimeError(
        f"No file found matching '{script_name}' in {repo} on branch {branch}. "
        f"Check spelling, capitalization, branch, and repo."
    )


def make_safe_filename(repo, file_path, branch):
    """
    Creates a Windows-safe filename using repo, script name, and branch.

    Example:
    my-org/my-repo, scripts/revenue_check.py, main
    becomes:
    my-org__my-repo__revenue_check__main.py
    """

    script_name = os.path.basename(file_path)
    name, extension = os.path.splitext(script_name)

    raw_filename = f"{repo.replace('/', '__')}__{name}__{branch}{extension}"

    invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']

    safe_filename = raw_filename

    for char in invalid_chars:
        safe_filename = safe_filename.replace(char, "_")

    return safe_filename
    
def parse_github_date(date_text):
    """
    Converts GitHub date text like 2026-06-06T14:32:19Z into a datetime.
    """
    if not date_text or date_text == "Unknown":
        return None

    try:
        return datetime.fromisoformat(date_text.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_date_status(date_a, date_b):
    """
    Compares two last modified dates.
    """
    parsed_a = parse_github_date(date_a)
    parsed_b = parse_github_date(date_b)

    if not parsed_a or not parsed_b:
        return "Unknown"

    difference_days = abs((parsed_a - parsed_b).days)

    if difference_days == 0:
        return "Same date"

    if difference_days <= 14:
        return "Within 2 weeks"

    return "Different date"


def read_file_content_without_header(local_path):
    """
    Reads a downloaded script but removes the audit metadata header before comparison.
    This avoids false differences caused only by evidence metadata, timestamps,
    Run IDs, SHA-256 hashes, Source URLs, Branch names, or Last Modified details.
    """
    with open(local_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    header_prefixes = (
        "# Tool:",
        "# Tool Version:",
        "# Retrieval Run ID:",
        "# Source:",
        "# Blame:",
        "# Repo path:",
        "# Branch:",
        "# Source Content SHA-256:",
        "# Evidence retrieved at UTC:",
        "# Evidence retrieved at local time:",
        "# Last modified:",
        "# Last modified by:",
        "# Last commit SHA:",
        "# Last commit message:",
        "# Last commit URL:",
        "# Saved File SHA-256:",
        "# Comparison Run ID:",
        "# Comparison generated at UTC:",
        "# Comparison generated at local time:",
        "# Comparison source:",
        "# Repo:",
        "# Script:",
        "# File A:",
        "# File A SHA-256:",
        "# File A Source Content SHA-256:",
        "# File B:",
        "# File B Source Content SHA-256:",
        "# File B SHA-256:",
        "# Branch A:",
        "# Branch A retrieval run ID:",
        "# Branch A evidence retrieved at UTC:",
        "# Branch A last modified:",
        "# Branch B:",
        "# Branch B retrieval run ID:",
        "# Branch B evidence retrieved at UTC:",
        "# Branch B last modified:",
        "# Unified diff begins below"
    )

    cleaned_lines = []
    skipping_header = True

    for line in lines:
        stripped = line.strip()

        if skipping_header:
            # Skip blank lines at the top of the downloaded file
            if not stripped:
                continue

            # Skip known metadata header lines
            if stripped.startswith(header_prefixes):
                continue

            # First non-metadata line means actual script content begins
            skipping_header = False

        cleaned_lines.append(line)

    return cleaned_lines


def make_safe_diff_filename(repo, github_path, branch_a, branch_b):
    """
    Creates a Windows-safe diff filename.
    """
    script_name = os.path.basename(github_path)
    name, extension = os.path.splitext(script_name)

    raw_filename = (
        f"{repo.replace('/', '__')}__"
        f"{name}__"
        f"{branch_a}_vs_{branch_b}.diff"
    )

    invalid_chars = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']

    safe_filename = raw_filename

    for char in invalid_chars:
        safe_filename = safe_filename.replace(char, "_")

    return safe_filename

def parse_metadata_from_downloaded_file(local_path):
    """
    Reads metadata from the header of a previously downloaded script.
    If metadata is missing, it falls back to local file information.
    """

    metadata = {
        "retrieval_run_id": "",
        "repo": "",
        "branch": "",
        "github_path": "",
        "local_path": local_path,
        "saved_file_sha256": "",
        "source_content_sha256": "",
        "evidence_retrieved_at_utc": "",
        "evidence_retrieved_at_local": "",
        "last_modified": "",
        "last_modified_by": "",
        "last_commit_message": "",
        "last_commit_sha": "",
        "last_commit_url": ""
    }

    try:
        with open(local_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        metadata["repo"] = "Selected local files"
        metadata["branch"] = os.path.basename(local_path)
        metadata["github_path"] = os.path.basename(local_path)

        try:
            metadata["saved_file_sha256"] = calculate_sha256(local_path)
        except Exception:
            metadata["saved_file_sha256"] = ""

        return metadata

    for line in lines[:50]:
        stripped = line.strip()

        if stripped.startswith("# Retrieval Run ID:"):
            metadata["retrieval_run_id"] = stripped.replace(
                "# Retrieval Run ID:", "", 1
            ).strip()

        elif stripped.startswith("# Repo path:"):
            repo_path = stripped.replace("# Repo path:", "", 1).strip()

            repo_path_parts = repo_path.split("/", 2)

            if len(repo_path_parts) == 3:
                metadata["repo"] = f"{repo_path_parts[0]}/{repo_path_parts[1]}"
                metadata["github_path"] = repo_path_parts[2]
            else:
                metadata["github_path"] = repo_path

        elif stripped.startswith("# Branch:"):
            metadata["branch"] = stripped.replace("# Branch:", "", 1).strip()
        
        elif stripped.startswith("# Source Content SHA-256:"):
            metadata["source_content_sha256"] = stripped.replace(
                "# Source Content SHA-256:", "", 1
            ).strip()

        elif stripped.startswith("# Evidence retrieved at UTC:"):
            metadata["evidence_retrieved_at_utc"] = stripped.replace(
                "# Evidence retrieved at UTC:", "", 1
            ).strip()

        elif stripped.startswith("# Evidence retrieved at local time:"):
            metadata["evidence_retrieved_at_local"] = stripped.replace(
                "# Evidence retrieved at local time:", "", 1
            ).strip()

        elif stripped.startswith("# Last modified:"):
            metadata["last_modified"] = stripped.replace(
                "# Last modified:", "", 1
            ).strip()

        elif stripped.startswith("# Last modified by:"):
            metadata["last_modified_by"] = stripped.replace(
                "# Last modified by:", "", 1
            ).strip()

        elif stripped.startswith("# Last commit message:"):
            metadata["last_commit_message"] = stripped.replace(
                "# Last commit message:", "", 1
            ).strip()

        elif stripped.startswith("# Last commit SHA:"):
            metadata["last_commit_sha"] = stripped.replace(
                "# Last commit SHA:", "", 1
            ).strip()

        elif stripped.startswith("# Last commit URL:"):
            metadata["last_commit_url"] = stripped.replace(
                "# Last commit URL:", "", 1
            ).strip()

    if not metadata["repo"]:
        metadata["repo"] = "Selected local files"

    if not metadata["github_path"]:
        metadata["github_path"] = os.path.basename(local_path)

    if not metadata["branch"]:
        metadata["branch"] = os.path.basename(local_path)

    try:
        metadata["saved_file_sha256"] = calculate_sha256(local_path)
    except Exception:
        metadata["saved_file_sha256"] = ""

    return metadata

def get_comparison_fieldnames():
    """
    Standard field order for comparison CSV files.
    Puts review conclusions first, followed by supporting evidence details.
    """
    return [
        "Tool",
        "Tool Version",
        "Comparison Run ID",
        "Repo",
        "Script",
        "Branch A",
        "Branch B",
        "Date Status",
        "Content Status",
        "Difference Summary",
        "Diff File",
        "Diff File SHA-256",
        "Compared At UTC",
        "Compared At Local Time",
        "Branch A Retrieval Run ID",
        "Branch A File",
        "Branch A File SHA-256",
        "Branch A Source Content SHA-256",
        "Branch A Retrieved At UTC",
        "Branch A Retrieved At Local Time",
        "Branch A Modified",
        "Branch B Retrieval Run ID",
        "Branch B File",
        "Branch B File SHA-256",
        "Branch B Source Content SHA-256",
        "Branch B Retrieved At UTC",
        "Branch B Retrieved At Local Time",
        "Branch B Modified"
    ]

def compare_downloaded_files():
    """
    Compares files downloaded in the current session.
    Groups by repo + GitHub path, then compares different branches.
    """

    if len(downloaded_files) < 2:
        messagebox.showwarning(
            "Not enough files",
            "Download at least two matching scripts from different branches first."
        )
        return

    save_folder = filedialog.askdirectory(
        title="Choose folder to save comparison results"
    )

    if not save_folder:
        return

    comparison_run_id = generate_run_id("COMPARE")
    comparison_timestamps = get_audit_timestamps()

    groups = {}

    for file_info in downloaded_files:
        key = (
            file_info["repo"].lower(),
            file_info["github_path"].lower()
        )

        groups.setdefault(key, []).append(file_info)

    comparison_rows = []

    for group_key, files in groups.items():
        if len(files) < 2:
            continue

        for i in range(len(files)):
            for j in range(i + 1, len(files)):
                file_a = files[i]
                file_b = files[j]

                if file_a["branch"] == file_b["branch"]:
                    continue

                content_a = read_file_content_without_header(file_a["local_path"])
                content_b = read_file_content_without_header(file_b["local_path"])

                date_status = get_date_status(
                    file_a["last_modified"],
                    file_b["last_modified"]
                )

                diff_file = "N/A"
                diff_file_sha256 = "N/A"

                if content_a == content_b:
                    content_status = "Same"
                    difference_summary = "No content differences"
                else:
                    content_status = "Different"

                    diff_lines = list(difflib.unified_diff(
                        content_a,
                        content_b,
                        fromfile=f"{file_a['branch']}/{file_a['github_path']}",
                        tofile=f"{file_b['branch']}/{file_b['github_path']}",
                        lineterm=""
                    ))

                    diff_filename = make_safe_diff_filename(
                        file_a["repo"],
                        file_a["github_path"],
                        file_a["branch"],
                        file_b["branch"]
                    )

                    diff_path = os.path.join(save_folder, diff_filename)

                    diff_metadata = [
                        f"# Tool: {APP_NAME}",
                        f"# Tool Version: {APP_VERSION}",
                        f"# Comparison Run ID: {comparison_run_id}",
                        f"# Comparison generated at UTC: {comparison_timestamps['utc']}",
                        f"# Comparison generated at local time: {comparison_timestamps['local']}",
                        f"# Comparison source: current session downloaded files",
                        f"# Repo: {file_a.get('repo', '')}",
                        f"# Script: {file_a.get('github_path', '')}",
                        f"# File A: {file_a.get('local_path', '')}",
                        f"# File A SHA-256: {file_a.get('saved_file_sha256', '')}",
                        f"# File A Source Content SHA-256: {file_a.get('source_content_sha256', '')}",
                        f"# Branch A: {file_a.get('branch', '')}",
                        f"# Branch A retrieval run ID: {file_a.get('retrieval_run_id', '')}",
                        f"# Branch A evidence retrieved at UTC: {file_a.get('evidence_retrieved_at_utc', '')}",
                        f"# Branch A last modified: {file_a.get('last_modified', '')}",
                        f"# File B: {file_b.get('local_path', '')}",
                        f"# File B SHA-256: {file_b.get('saved_file_sha256', '')}",
                        f"# File B Source Content SHA-256: {file_b.get('source_content_sha256', '')}",
                        f"# Branch B: {file_b.get('branch', '')}",
                        f"# Branch B retrieval run ID: {file_b.get('retrieval_run_id', '')}",
                        f"# Branch B evidence retrieved at UTC: {file_b.get('evidence_retrieved_at_utc', '')}",
                        f"# Branch B last modified: {file_b.get('last_modified', '')}",
                        "",
                        "# Unified diff begins below",
                        ""
                    ]

                    with open(diff_path, "w", encoding="utf-8", errors="replace") as f:
                        f.write("\n".join(diff_metadata))
                        f.write("\n")
                        f.write("\n".join(diff_lines))

                    diff_file = diff_path
                    diff_file_sha256 = calculate_sha256(diff_path)

                    added_lines = sum(
                        1 for line in diff_lines
                        if line.startswith("+") and not line.startswith("+++")
                    )

                    removed_lines = sum(
                        1 for line in diff_lines
                        if line.startswith("-") and not line.startswith("---")
                    )

                    difference_summary = (
                        f"{added_lines} added line(s), "
                        f"{removed_lines} removed line(s)"
                    )
                    
                comparison_rows.append({
                    "Tool": APP_NAME,
                    "Tool Version": APP_VERSION,
                    "Comparison Run ID": comparison_run_id,
                    "Compared At UTC": comparison_timestamps["utc"],
                    "Compared At Local Time": comparison_timestamps["local"],
                    "Repo": file_a["repo"],
                    "Script": file_a["github_path"],
                    "Branch A": file_a["branch"],
                    "Branch A File": file_a["local_path"],
                    "Branch A Retrieval Run ID": file_a.get("retrieval_run_id", ""),
                    "Branch A File SHA-256": file_a.get("saved_file_sha256", ""),
                    "Branch A Source Content SHA-256": file_a.get("source_content_sha256", ""),
                    "Branch A Retrieved At UTC": file_a.get("evidence_retrieved_at_utc", ""),
                    "Branch A Retrieved At Local Time": file_a.get("evidence_retrieved_at_local", ""),
                    "Branch A Modified": file_a["last_modified"],
                    "Branch B": file_b["branch"],
                    "Branch B File": file_b["local_path"],
                    "Branch B Retrieval Run ID": file_b.get("retrieval_run_id", ""),
                    "Branch B File SHA-256": file_b.get("saved_file_sha256", ""),
                    "Branch B Source Content SHA-256": file_b.get("source_content_sha256", ""),
                    "Branch B Retrieved At UTC": file_b.get("evidence_retrieved_at_utc", ""),
                    "Branch B Retrieved At Local Time": file_b.get("evidence_retrieved_at_local", ""),
                    "Branch B Modified": file_b["last_modified"],
                    "Date Status": date_status,
                    "Content Status": content_status,
                    "Difference Summary": difference_summary,
                    "Diff File": diff_file,
                    "Diff File SHA-256": diff_file_sha256,
                })

    if not comparison_rows:
        messagebox.showinfo(
            "No comparisons found",
            "No matching scripts from different branches were found in the current session."
        )
        return

    summary_csv_path = os.path.join(
        save_folder,
        f"downloaded_file_comparison_summary_{comparison_run_id}.csv"
    )

    with open(summary_csv_path, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = get_comparison_fieldnames()

        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(comparison_rows)

    table_lines = []
    table_lines.append("Downloaded File Comparison Summary")
    table_lines.append("=" * 120)
    table_lines.append(f"Comparison Run ID: {comparison_run_id}")
    table_lines.append(f"Comparison generated at UTC: {comparison_timestamps['utc']}")
    table_lines.append(f"Comparison generated at local time: {comparison_timestamps['local']}")
    table_lines.append(f"Summary CSV: {summary_csv_path}")
    table_lines.append("")
    table_lines.append(
        f"{'Run ID':24} | {'Repo':30} | {'Script':45} | "
        f"{'Branch A':18} | {'Branch B':18} | {'Date Status':18} | "
        f"{'Content':10} | {'Difference Summary':30} | {'Diff File'}"
    )
    table_lines.append("-" * 240)

    for row in comparison_rows:
        table_lines.append(
            f"{row['Comparison Run ID'][:24]:24} | "
            f"{row['Repo'][:30]:30} | "
            f"{row['Script'][:45]:45} | "
            f"{row['Branch A'][:18]:18} | "
            f"{row['Branch B'][:18]:18} | "
            f"{row['Date Status'][:18]:18} | "
            f"{row['Content Status'][:10]:10} | "
            f"{row['Difference Summary'][:30]:30} | "
            f"{row['Diff File']}"
        )

    existing_output = output_text.get("1.0", tk.END).strip()

    if existing_output:
        output_text.insert(tk.END, "\n\n")
        output_text.insert(tk.END, "=" * 120)
        output_text.insert(tk.END, "\nNEW DOWNLOADED FILE COMPARISON\n")
        output_text.insert(tk.END, "=" * 120)
        output_text.insert(tk.END, "\n\n")

    output_text.insert(tk.END, "\n".join(table_lines))
    output_text.see(tk.END)

    messagebox.showinfo(
        "Comparison complete",
        f"Compared downloaded files.\n\nSummary saved to:\n{summary_csv_path}"
    )

def get_audit_timestamps():
    """
    Returns UTC and local timestamps for audit evidence.
    UTC is preferred for audit consistency.
    Local is included for user readability.
    """
    utc_now = datetime.now(timezone.utc)
    local_now = datetime.now().astimezone()

    return {
        "utc": utc_now.isoformat(timespec="seconds"),
        "local": local_now.isoformat(timespec="seconds")
    }

def generate_run_id(prefix):
    """
    Creates a unique Run ID for audit evidence.
    Example:
    RETRIEVAL_20260607_114210
    COMPARE_20260607_114522
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{timestamp}"

def calculate_text_sha256(text):
    """
    Calculates SHA-256 hash for text content.
    Used for hashing the original GitHub source content before metadata headers are added.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def calculate_sha256(file_path):
    """
    Calculates the SHA-256 hash of a saved file.
    This can be used later to confirm the file was not changed.
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()

def retrieve_script():
    default_repo = repo_entry.get().strip()
    default_branch = branch_entry.get().strip()
    single_script_name = script_entry.get().strip()

    script_list_raw = script_list_text.get("1.0", tk.END).strip()

    try:
        script_requests = []

        if script_list_raw:
            for line in script_list_raw.splitlines():
                if line.strip():
                    parsed = parse_script_line(line, default_repo, default_branch)
                    if parsed:
                        script_requests.append(parsed)
        elif single_script_name:
            if not default_repo or not default_branch:
                messagebox.showerror("Missing information", "Please enter repo and branch.")
                return

            script_requests.append({
                "repo": default_repo,
                "branch": default_branch,
                "script_name": single_script_name
            })
        else:
            messagebox.showerror(
                "Missing information",
                "Please enter a script name/path or paste a list of scripts."
            )
            return

        for request in script_requests:
            if not request["repo"] or not request["branch"] or not request["script_name"]:
                raise RuntimeError(
                    "Each script request needs repo, branch, and script path.\n\n"
                    "Use either:\n"
                    "path/to/script.py\n"
                    "or\n"
                    "org/repo | branch | path/to/script.py"
                )

        save_folder = filedialog.askdirectory(
            title="Choose folder to save downloaded scripts"
        )

        if not save_folder:
            return

        retrieval_run_id = generate_run_id("RETRIEVAL")

        status_label.config(text="Checking GitHub authentication...")
        root.update_idletasks()

        if not confirm_authenticated():
            raise RuntimeError("You are not authenticated. Please run: gh auth login")

        token = get_github_token()

        successful_downloads = []
        failed_downloads = []
        summary_rows = []

        for request in script_requests:
            repo = request["repo"]
            branch = request["branch"]
            script_name = request["script_name"]

            try:
                status_label.config(text=f"Finding script: {repo} / {branch} / {script_name}")
                root.update_idletasks()

                file_path = resolve_file_path(repo, branch, script_name, token)

                status_label.config(text=f"Retrieving script: {repo} / {branch} / {file_path}")
                root.update_idletasks()

                content = retrieve_file(repo, branch, file_path, token)
                source_content_sha256 = calculate_text_sha256(content)

                last_modified = get_last_modified_info(repo, branch, file_path, token)

                full_script_url = f"https://github.com/{repo}/blob/{branch}/{file_path}"
                blame_url = f"https://github.com/{repo}/blame/{branch}/{file_path}"

                retrieved_timestamps = get_audit_timestamps()
                
                content_with_path = (
                    f"# Tool: {APP_NAME}\n"
                    f"# Tool Version: {APP_VERSION}\n"
                    f"# Retrieval Run ID: {retrieval_run_id}\n"
                    f"# Source: {full_script_url}\n"
                    f"# Blame: {blame_url}\n"
                    f"# Repo path: {repo}/{file_path}\n"
                    f"# Branch: {branch}\n"
                    f"# Source Content SHA-256: {source_content_sha256}\n"
                    f"# Evidence retrieved at UTC: {retrieved_timestamps['utc']}\n"
                    f"# Evidence retrieved at local time: {retrieved_timestamps['local']}\n"
                    f"# Last modified: {last_modified['date']}\n"
                    f"# Last modified by: {last_modified['author']}\n"
                    f"# Last commit SHA: {last_modified['sha']}\n"
                    f"# Last commit message: {last_modified['message']}\n"
                    f"# Last commit URL: {last_modified['url']}\n\n"
                    f"{content}"
                )

                safe_filename = make_safe_filename(repo, file_path, branch)
                save_path = os.path.join(save_folder, safe_filename)

                with open(save_path, "w", encoding="utf-8") as f:
                    f.write(content_with_path)
                
                saved_file_sha256 = calculate_sha256(save_path)
                
                downloaded_files.append({
                    "retrieval_run_id": retrieval_run_id,
                    "repo": repo,
                    "branch": branch,
                    "github_path": file_path,
                    "local_path": save_path,
                    "saved_file_sha256": saved_file_sha256,
                    "source_content_sha256": source_content_sha256,
                    "evidence_retrieved_at_utc": retrieved_timestamps["utc"],
                    "evidence_retrieved_at_local": retrieved_timestamps["local"],
                    "last_modified": last_modified["date"],
                    "last_modified_by": last_modified["author"],
                    "last_commit_message": last_modified["message"],
                    "last_commit_sha": last_modified["sha"],
                    "last_commit_url": last_modified["url"]
                })

                summary_rows.append({
                    "Tool": APP_NAME,
                    "Tool Version": APP_VERSION,
                    "Retrieval Run ID": retrieval_run_id,
                    "Repo": repo,
                    "Branch": branch,
                    "Script": file_path,
                    "Evidence Retrieved At UTC": retrieved_timestamps["utc"],
                    "Evidence Retrieved At Local Time": retrieved_timestamps["local"],
                    "Last Modified": last_modified["date"],
                    "Last Modified By": last_modified["author"],
                    "Last Commit Message": last_modified["message"],
                    "Last Commit SHA": last_modified["sha"],
                    "Last Commit URL": last_modified["url"],
                    "Saved File": save_path,
                    "Saved File SHA-256": saved_file_sha256,
                    "Source Content SHA-256": source_content_sha256,
                })

                successful_downloads.append(save_path)
                                
            except Exception as script_error:
                failed_downloads.append(
                    f"{repo} | {branch} | {script_name}: {script_error}"
                )

        summary_csv_path = ""

        if summary_rows:
            summary_csv_path = os.path.join(save_folder, f"download_summary_{retrieval_run_id}.csv")

            with open(summary_csv_path, "w", newline="", encoding="utf-8") as csvfile:
                fieldnames = [
                    "Tool",
                    "Tool Version",
                    "Retrieval Run ID",
                    "Repo",
                    "Branch",
                    "Script",
                    "Evidence Retrieved At UTC",
                    "Evidence Retrieved At Local Time",
                    "Last Modified",
                    "Last Modified By",
                    "Last Commit Message",
                    "Last Commit SHA",
                    "Last Commit URL",
                    "Saved File",
                    "Saved File SHA-256",
                    "Source Content SHA-256"
                ]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(summary_rows)

        summary_lines = []
        summary_lines.append("Download Summary")
        summary_lines.append("=" * 120)
        summary_lines.append(f"Retrieval Run ID: {retrieval_run_id}")

        if summary_csv_path:
            summary_lines.append(f"Summary CSV: {summary_csv_path}")

        summary_lines.append("")
        summary_lines.append(
            f"{'Repo':30} | {'Branch':18} | {'Script':45} | "
            f"{'Retrieved UTC':25} | {'Last Modified':22} | "
            f"{'Modified By':25} | {'File SHA':12} | {'Source SHA':12} | {'Last Commit Message'}"
        )
        summary_lines.append("-" * 250)

        for row in summary_rows:
            summary_lines.append(
                f"{row['Repo'][:30]:30} | "
                f"{row['Branch'][:18]:18} | "
                f"{row['Script'][:45]:45} | "
                f"{row['Evidence Retrieved At UTC'][:25]:25} | "
                f"{row['Last Modified'][:22]:22} | "
                f"{row['Last Modified By'][:25]:25} | "
                f"{row['Saved File SHA-256'][:12]:12} | "
                f"{row['Source Content SHA-256'][:12]:12} | "
                f"{row['Last Commit Message'][:80]}"
            )

        if failed_downloads:
            summary_lines.append("")
            summary_lines.append("Failed Downloads")
            summary_lines.append("=" * 120)

            for failure in failed_downloads:
                summary_lines.append(failure)

        # Add separator if the output box already has content
        existing_output = output_text.get("1.0", tk.END).strip()

        if existing_output:
            output_text.insert(tk.END, "\n\n")
            output_text.insert(tk.END, "=" * 120)
            output_text.insert(tk.END, "\nNEW DOWNLOAD RUN\n")
            output_text.insert(tk.END, "=" * 120)
            output_text.insert(tk.END, "\n\n")

        # Display only the download summary in the app window.
        # The actual script contents are saved in the individual downloaded files.
        output_text.insert(tk.END, "\n".join(summary_lines))

        # Scroll to the bottom so the latest summary is visible
        output_text.see(tk.END)

        status_label.config(
            text=f"Saved {len(successful_downloads)} script(s). "
                 f"Failed: {len(failed_downloads)}."
        )

        message = f"Successfully saved {len(successful_downloads)} script(s)."

        if summary_csv_path:
            message += f"\n\nSummary CSV:\n{summary_csv_path}"

        if successful_downloads:
            message += "\n\nSaved files:\n" + "\n".join(successful_downloads)

        if failed_downloads:
            message += "\n\nFailed:\n" + "\n".join(failed_downloads)

        messagebox.showinfo("Download complete", message)

    except Exception as e:
        status_label.config(text="Error")
        messagebox.showerror("Error", str(e))

def copy_to_clipboard():
    content = output_text.get("1.0", tk.END).strip()

    if not content:
        messagebox.showwarning("Nothing to copy", "No script has been retrieved yet.")
        return

    root.clipboard_clear()
    root.clipboard_append(content)
    root.update()

    messagebox.showinfo("Copied", "Script copied to clipboard.")


def save_output_summary():
    content = output_text.get("1.0", tk.END).strip()

    if not content:
        messagebox.showwarning("Nothing to save", "No output summary is currently displayed.")
        return

    file_path = filedialog.asksaveasfilename(
        title="Save script as",
        defaultextension=".txt",
        filetypes=[
            ("Python files", "*.py"),
            ("Shell scripts", "*.sh"),
            ("SQL files", "*.sql"),
            ("PowerShell files", "*.ps1"),
            ("Text files", "*.txt"),
            ("All files", "*.*")
        ]
    )

    if not file_path:
        return

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    messagebox.showinfo("Saved", f"Script saved to:\n{file_path}")

def clear_session():
    """
    Clears the current app session's downloaded file tracking list.
    This does not delete any downloaded files, summaries, or diff files from disk.
    """
    if not downloaded_files:
        messagebox.showinfo(
            "Session already clear",
            "There are no downloaded files currently tracked in this app session."
        )
        return

    confirm = messagebox.askyesno(
        "Clear session?",
        "This will clear the app's current downloaded-file tracking list.\n\n"
        "It will NOT delete any saved scripts, summaries, or diff files from your computer.\n\n"
        "After clearing, Compare Downloaded Files will only compare files downloaded after this point.\n\n"
        "Do you want to continue?"
    )

    if not confirm:
        return

    downloaded_count = len(downloaded_files)
    downloaded_files.clear()

    status_label.config(text="Session cleared.")
    output_text.delete("1.0", tk.END)
    output_text.insert(
        tk.END,
        f"Session cleared.\n\n"
        f"Cleared {downloaded_count} tracked downloaded file(s).\n\n"
        f"No saved evidence files were deleted from your computer."
    )

    messagebox.showinfo(
        "Session cleared",
        f"Cleared {downloaded_count} tracked downloaded file(s).\n\n"
        "No saved files were deleted."
    )

root = tk.Tk()
root.title(f"{APP_NAME} v{APP_VERSION}")
root.geometry("900x650")

frame = tk.Frame(root, padx=12, pady=12)
frame.pack(fill=tk.BOTH, expand=True)

tk.Label(frame, text="Repository, e.g. org/repo").grid(row=0, column=0, sticky="w")
repo_entry = tk.Entry(frame, width=60)
repo_entry.grid(row=0, column=1, sticky="we", pady=4)

tk.Label(frame, text="Branch, e.g. main").grid(row=1, column=0, sticky="w")
branch_entry = tk.Entry(frame, width=60)
branch_entry.insert(0, "main")
branch_entry.grid(row=1, column=1, sticky="we", pady=4)

tk.Label(frame, text="Script name or path").grid(row=2, column=0, sticky="w")
script_entry = tk.Entry(frame, width=60)
script_entry.grid(row=2, column=1, sticky="we", pady=4)

tk.Label(
    frame,
    text="Or paste multiple scripts. Use path only, or: org/repo | branch | path"
).grid(row=3, column=0, sticky="nw")

script_list_text = tk.Text(frame, height=6, width=60)
script_list_text.grid(row=3, column=1, sticky="we", pady=4)

def compare_selected_files():
    """
    Lets the user select previously downloaded files and compare them locally.
    This does not call GitHub.

    If metadata is available, files are grouped by repo + GitHub path.
    If exactly two files are selected and metadata does not match, the app compares them directly.
    """

    selected_files = filedialog.askopenfilenames(
        title="Select downloaded files to compare",
        filetypes=[
            ("All files", "*.*"),
            ("Python files", "*.py"),
            ("SQL files", "*.sql"),
            ("PowerShell files", "*.ps1"),
            ("Text files", "*.txt"),
            ("Diff files", "*.diff")
        ]
    )

    if not selected_files:
        return

    if len(selected_files) < 2:
        messagebox.showwarning(
            "Not enough files",
            "Please select at least two files to compare."
        )
        return

    save_folder = filedialog.askdirectory(
        title="Choose folder to save selected-file comparison results"
    )

    if not save_folder:
        return

    try:
        comparison_run_id = generate_run_id("COMPARE_SELECTED")
        comparison_timestamps = get_audit_timestamps()

        selected_file_infos = [
            parse_metadata_from_downloaded_file(local_path)
            for local_path in selected_files
        ]

        groups = {}

        for file_info in selected_file_infos:
            key = (
                file_info.get("repo", "").lower(),
                file_info.get("github_path", "").lower()
            )

            groups.setdefault(key, []).append(file_info)

        comparison_pairs = []

        # Normal behavior: compare files with matching repo + GitHub path metadata.
        for group_key, files in groups.items():
            if len(files) < 2:
                continue

            for i in range(len(files)):
                for j in range(i + 1, len(files)):
                    file_a = files[i]
                    file_b = files[j]

                    if file_a["local_path"] == file_b["local_path"]:
                        continue

                    comparison_pairs.append((file_a, file_b))

        # Fallback behavior: if no metadata-based pairs were found
        # and the user selected exactly two files, compare those two directly.
        if not comparison_pairs and len(selected_file_infos) == 2:
            file_a = selected_file_infos[0]
            file_b = selected_file_infos[1]

            if not file_a.get("repo"):
                file_a["repo"] = "Selected local files"

            if not file_b.get("repo"):
                file_b["repo"] = "Selected local files"

            if not file_a.get("github_path"):
                file_a["github_path"] = os.path.basename(file_a["local_path"])

            if not file_b.get("github_path"):
                file_b["github_path"] = os.path.basename(file_b["local_path"])

            if not file_a.get("branch"):
                file_a["branch"] = os.path.basename(file_a["local_path"])

            if not file_b.get("branch"):
                file_b["branch"] = os.path.basename(file_b["local_path"])

            comparison_pairs.append((file_a, file_b))

        if not comparison_pairs:
            messagebox.showinfo(
                "No matching comparisons found",
                "No selected files had matching repo and script path metadata.\n\n"
                "Tip: Select exactly two files if you want to force a direct comparison."
            )
            return

        comparison_rows = []

        for file_a, file_b in comparison_pairs:
            diff_file = "N/A"
            diff_file_sha256 = "N/A"

            content_a = read_file_content_without_header(file_a["local_path"])
            content_b = read_file_content_without_header(file_b["local_path"])

            date_status = get_date_status(
                file_a.get("last_modified", ""),
                file_b.get("last_modified", "")
            )

            if content_a == content_b:
                content_status = "Same"
                difference_summary = "No content differences"
            else:
                content_status = "Different"

                diff_lines = list(difflib.unified_diff(
                    content_a,
                    content_b,
                    fromfile=f"{file_a.get('branch', '')}/{file_a.get('github_path', '')}",
                    tofile=f"{file_b.get('branch', '')}/{file_b.get('github_path', '')}",
                    lineterm=""
                ))

                diff_filename = make_safe_diff_filename(
                    file_a.get("repo", "selected-files"),
                    file_a.get("github_path", os.path.basename(file_a["local_path"])),
                    file_a.get("branch", "file-a"),
                    file_b.get("branch", "file-b")
                )

                diff_path = os.path.join(save_folder, diff_filename)

                diff_metadata = [
                    f"# Tool: {APP_NAME}",
                    f"# Tool Version: {APP_VERSION}",
                    f"# Comparison Run ID: {comparison_run_id}",
                    f"# Comparison generated at UTC: {comparison_timestamps['utc']}",
                    f"# Comparison generated at local time: {comparison_timestamps['local']}",
                    f"# Comparison source: selected local files",
                    f"# Repo: {file_a.get('repo', '')}",
                    f"# Script: {file_a.get('github_path', '')}",
                    f"# File A: {file_a.get('local_path', '')}",
                    f"# File A SHA-256: {file_a.get('saved_file_sha256', '')}",
                    f"# File A Source Content SHA-256: {file_a.get('source_content_sha256', '')}",
                    f"# Branch A: {file_a.get('branch', '')}",
                    f"# Branch A retrieval run ID: {file_a.get('retrieval_run_id', '')}",
                    f"# Branch A evidence retrieved at UTC: {file_a.get('evidence_retrieved_at_utc', '')}",
                    f"# Branch A last modified: {file_a.get('last_modified', '')}",
                    f"# File B: {file_b.get('local_path', '')}",
                    f"# File B SHA-256: {file_b.get('saved_file_sha256', '')}",
                    f"# File B Source Content SHA-256: {file_b.get('source_content_sha256', '')}",
                    f"# Branch B: {file_b.get('branch', '')}",
                    f"# Branch B retrieval run ID: {file_b.get('retrieval_run_id', '')}",
                    f"# Branch B evidence retrieved at UTC: {file_b.get('evidence_retrieved_at_utc', '')}",
                    f"# Branch B last modified: {file_b.get('last_modified', '')}",
                    "",
                    "# Unified diff begins below",
                    ""
                ]

                with open(diff_path, "w", encoding="utf-8", errors="replace") as f:
                    f.write("\n".join(diff_metadata))
                    f.write("\n")
                    f.write("\n".join(diff_lines))

                diff_file = diff_path
                diff_file_sha256 = calculate_sha256(diff_path)

                added_lines = sum(
                    1 for line in diff_lines
                    if line.startswith("+") and not line.startswith("+++")
                )

                removed_lines = sum(
                    1 for line in diff_lines
                    if line.startswith("-") and not line.startswith("---")
                )

                difference_summary = (
                    f"{added_lines} added line(s), "
                    f"{removed_lines} removed line(s)"
                )

            comparison_rows.append({
                "Tool": APP_NAME,
                "Tool Version": APP_VERSION,                
                "Comparison Run ID": comparison_run_id,
                "Compared At UTC": comparison_timestamps["utc"],
                "Compared At Local Time": comparison_timestamps["local"],
                "Comparison Source": "Selected local files",
                "Repo": file_a.get("repo", ""),
                "Script": file_a.get("github_path", ""),
                "Branch A": file_a.get("branch", ""),
                "Branch A Retrieval Run ID": file_a.get("retrieval_run_id", ""),
                "Branch A File": file_a.get("local_path", ""),
                "Branch A File SHA-256": file_a.get("saved_file_sha256", ""),
                "Branch A Source Content SHA-256": file_a.get("source_content_sha256", ""),
                "Branch A Retrieved At UTC": file_a.get("evidence_retrieved_at_utc", ""),
                "Branch A Retrieved At Local Time": file_a.get("evidence_retrieved_at_local", ""),
                "Branch A Modified": file_a.get("last_modified", ""),
                "Branch B": file_b.get("branch", ""),
                "Branch B Retrieval Run ID": file_b.get("retrieval_run_id", ""),
                "Branch B File": file_b.get("local_path", ""),
                "Branch B File SHA-256": file_b.get("saved_file_sha256", ""),
                "Branch B Source Content SHA-256": file_b.get("source_content_sha256", ""),
                "Branch B Retrieved At UTC": file_b.get("evidence_retrieved_at_utc", ""),
                "Branch B Retrieved At Local Time": file_b.get("evidence_retrieved_at_local", ""),
                "Branch B Modified": file_b.get("last_modified", ""),
                "Date Status": date_status,
                "Content Status": content_status,
                "Difference Summary": difference_summary,
                "Diff File": diff_file,
                "Diff File SHA-256": diff_file_sha256
            })

        summary_csv_path = os.path.join(
            save_folder,
            f"selected_file_comparison_summary_{comparison_run_id}.csv"
        )

        with open(summary_csv_path, "w", newline="", encoding="utf-8") as csvfile:
            fieldnames = get_comparison_fieldnames()

            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(comparison_rows)

        summary_csv_sha256 = calculate_sha256(summary_csv_path)

        table_lines = []
        table_lines.append("Selected File Comparison Summary")
        table_lines.append("=" * 120)
        table_lines.append(f"Comparison Run ID: {comparison_run_id}")
        table_lines.append(f"Comparison generated at UTC: {comparison_timestamps['utc']}")
        table_lines.append(f"Comparison generated at local time: {comparison_timestamps['local']}")
        table_lines.append(f"Summary CSV: {summary_csv_path}")
        table_lines.append(f"Summary CSV SHA-256: {summary_csv_sha256}")
        table_lines.append("")
        table_lines.append(
            f"{'Run ID':24} | {'Repo':30} | {'Script':45} | "
            f"{'Branch A':18} | {'Branch B':18} | {'Date Status':18} | "
            f"{'Content':10} | {'Difference Summary':30} | {'Diff File'}"
        )
        table_lines.append("-" * 240)

        for row in comparison_rows:
            table_lines.append(
                f"{row['Comparison Run ID'][:24]:24} | "
                f"{row['Repo'][:30]:30} | "
                f"{row['Script'][:45]:45} | "
                f"{row['Branch A'][:18]:18} | "
                f"{row['Branch B'][:18]:18} | "
                f"{row['Date Status'][:18]:18} | "
                f"{row['Content Status'][:10]:10} | "
                f"{row['Difference Summary'][:30]:30} | "
                f"{row['Diff File']}"
            )

        existing_output = output_text.get("1.0", tk.END).strip()

        if existing_output:
            output_text.insert(tk.END, "\n\n")
            output_text.insert(tk.END, "=" * 120)
            output_text.insert(tk.END, "\nNEW SELECTED FILE COMPARISON\n")
            output_text.insert(tk.END, "=" * 120)
            output_text.insert(tk.END, "\n\n")

        output_text.insert(tk.END, "\n".join(table_lines))
        output_text.see(tk.END)

        messagebox.showinfo(
            "Selected file comparison complete",
            f"Compared selected files.\n\nSummary saved to:\n{summary_csv_path}"
        )

    except Exception as e:
        messagebox.showerror("Compare selected files error", str(e))

button_frame = tk.Frame(frame)
button_frame.grid(row=4, column=0, columnspan=2, sticky="w", pady=10)

tk.Button(button_frame, text="Retrieve Script", command=retrieve_script).pack(side=tk.LEFT, padx=4)
tk.Button(button_frame, text="Compare Downloaded Files", command=compare_downloaded_files).pack(side=tk.LEFT, padx=4)
tk.Button(button_frame, text="Compare Selected Files", command=compare_selected_files).pack(side=tk.LEFT, padx=4)
tk.Button(button_frame, text="Clear Session", command=clear_session).pack(side=tk.LEFT, padx=4)
tk.Button(button_frame, text="Copy to Clipboard", command=copy_to_clipboard).pack(side=tk.LEFT, padx=4)
tk.Button(button_frame, text="Save Output Summary", command=save_output_summary).pack(side=tk.LEFT, padx=4)

frame.columnconfigure(1, weight=1)
frame.rowconfigure(6, weight=1)
status_label = tk.Label(frame, text="Ready", anchor="w")
status_label.grid(row=5, column=0, columnspan=2, sticky="we", pady=4)

output_text = tk.Text(frame, wrap=tk.NONE)
output_text.grid(row=6, column=0, columnspan=2, sticky="nsew", pady=8)

frame.columnconfigure(1, weight=1)
frame.rowconfigure(6, weight=1)

root.mainloop()