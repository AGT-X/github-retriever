# GitHub Retriever

**GitHub Retriever** is a lightweight desktop tool that helps auditors and technical teams retrieve, compare, and document scripts from GitHub repositories.

It was built to make source-code evidence collection easier, cleaner, and more repeatable.

## What it does

- Retrieves scripts from GitHub by repository, branch, and file path
- Supports single-file and batch retrieval
- Saves retrieved files with metadata headers
- Captures useful evidence metadata, including:
  - repository
  - branch
  - script path
  - retrieval timestamp
  - last modified date
  - last commit message
  - last modified by
  - SHA-256 hash
- Compares scripts across branches or downloaded files
- Generates diff files and comparison summaries
- Produces CSV summaries suitable for audit documentation

## Why this exists

Auditors often need to obtain and compare scripts as part of SOX control testing or other control testing procedures. Manually retrieving code, documenting metadata, and comparing changes can be repetitive and error-prone.

GitHub Retriever helps make that process more consistent and transparent.

## Requirements

- Python 3.10 or later
- GitHub CLI installed and authenticated
- Access to the target GitHub repositories

## Setup

Clone the repository:

```bash
git clone https://github.com/YOUR-USERNAME/github-retriever.git
cd github-retriever
