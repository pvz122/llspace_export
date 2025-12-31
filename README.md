# llspace Exporter

A desktop GUI tool to export user card content from the llspace platform.

## Requirements

- Python 3.9+
- `uv` package manager (recommended)

## Installation

1. Initialize the project environment:
   ```bash
   uv sync
   ```

## Usage

1. Run the exporter:
   ```bash
   uv run llspace_exporter.py
   ```

2. Enter your llspace username and password.
3. Select a card package to export.
4. Wait for the export to complete. The output will be saved in a new directory named `{package_name}_{timestamp}`.

## Features

- Exports cards to Markdown format.
- Downloads all card cover images.
- Creates offline-viewable HTML snapshots of linked web pages.
- Generates an index HTML file for easy browsing.
