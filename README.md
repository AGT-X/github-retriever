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
git clone https://github.com/AGT-X/github-retriever.git
cd github-retriever
```

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Authenticate with GitHub CLI

GitHub Retriever uses the GitHub CLI to access repositories that you are authorized to view.

```bash
gh auth login
```

Follow the prompts to authenticate with your GitHub account.

### 3. Run GitHub Retriever

```bash
python github_retriever.py
```

## Security and Authorized Use

Only use GitHub Retriever with repositories and files you are authorized to access.

Do not use this tool to publish, expose, or distribute confidential source code, audit evidence, client data, credentials, tokens, or proprietary repository information.

## Professional Use Disclaimer

GitHub Retriever is designed to support evidence retrieval and comparison workflows. It does not replace professional judgment, audit methodology, control testing standards, or organizational review procedures.

Users are responsible for validating all outputs before relying on them for audit, compliance, or reporting purposes.

## License

This project is licensed under the MIT License.

## Commercial Use Notice

GitHub Retriever is shared to support the audit, compliance, and technology community.

Please do not sell this tool, repackage it as a commercial product, or represent it as your own commercial offering without permission from the author.

Organizations and individuals may use the tool internally, but the intent of this project is community benefit, learning, and practical audit support.

##Author

Created by Alfredo Tapia