"""Project path encoding/decoding for Claude Code folder names."""

import os


def decode_project_path(folder_name: str) -> str:
    """
    Convert Claude Code folder name to filesystem path.

    Claude Code encodes project paths in folder names:
    - /Users/samotage/dev/project -> -Users-samotage-dev-project
    - The leading slash becomes a leading dash
    - Subsequent slashes become dashes

    Note: This encoding is lossy — path components containing literal dashes
    (e.g., /my-project/) are indistinguishable from directory separators after
    encoding. This is a Claude Code upstream limitation; there is no escaping
    mechanism in the folder naming convention.

    Args:
        folder_name: Folder name from ~/.claude/projects/

    Returns:
        Filesystem path
    """
    if not folder_name:
        return ""

    # Replace leading dash with slash, then all remaining dashes with slashes
    # The folder name starts with a dash representing the leading slash
    if folder_name.startswith("-"):
        path = "/" + folder_name[1:].replace("-", "/")
    else:
        path = folder_name.replace("-", "/")

    return path


def encode_project_path(path: str) -> str:
    """
    Convert filesystem path to Claude Code folder name.

    This is the reverse of decode_project_path.

    Args:
        path: Filesystem path

    Returns:
        Folder name for ~/.claude/projects/
    """
    if not path:
        return ""

    # Normalize path (remove trailing slashes, etc.)
    path = os.path.normpath(path)

    # Replace slashes with dashes
    # The leading slash becomes a leading dash
    if path.startswith("/"):
        folder_name = "-" + path[1:].replace("/", "-")
    else:
        folder_name = path.replace("/", "-")

    return folder_name


def locate_jsonl_file(
    working_directory: str, projects_path: str = "~/.claude/projects"
) -> str | None:
    """
    Locate the most recent jsonl file for a working directory.

    Args:
        working_directory: The project's working directory
        projects_path: Path to Claude Code projects directory

    Returns:
        Path to the most recent jsonl file, or None if not found
    """
    projects_path = os.path.expanduser(projects_path)
    folder_name = encode_project_path(working_directory)
    project_folder = os.path.join(projects_path, folder_name)

    if not os.path.isdir(project_folder):
        return None

    # Find all jsonl files in the folder
    jsonl_files = []
    for filename in os.listdir(project_folder):
        if filename.endswith(".jsonl"):
            filepath = os.path.join(project_folder, filename)
            jsonl_files.append((filepath, os.path.getmtime(filepath)))

    if not jsonl_files:
        return None

    # Return the most recently modified file
    jsonl_files.sort(key=lambda x: x[1], reverse=True)
    return jsonl_files[0][0]
