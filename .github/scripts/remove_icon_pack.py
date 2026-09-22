#!/usr/bin/env python3
"""Remove one stored SVG icon and its associated repository assets."""

import argparse
import json
from pathlib import Path
import re
import sys

from process_icon_submission import SubmissionError, metadata_by_id, read_metadata


def validate_path(path: Path) -> None:
    for parent in [path, *path.parents]:
        if parent.is_symlink():
            raise SubmissionError(f'Refusing symlink: {parent}')
    if path.exists() and not path.is_file():
        raise SubmissionError(f'Expected a regular file: {path}')


def remove_icon_pack(name: str) -> None:
    if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*(?:\.svg)?', name) is None:
        raise SubmissionError('Use an exact filename from svg/, with or without .svg.')
    filename = name if name.endswith('.svg') else f'{name}.svg'
    metadata_path = Path('metadata.json')
    validate_path(metadata_path)
    metadata = read_metadata(metadata_path)
    metadata_by_id(metadata, 'metadata.json')
    matches = [entry for entry in metadata if entry.get('Source') == filename]
    if len(matches) != 1:
        raise SubmissionError(f'Expected exactly one metadata entry for {filename}; found {len(matches)}.')
    entry = matches[0]
    identifier = str(entry['Id'])
    source = Path('svg') / filename
    validate_path(source)
    if not source.is_file():
        raise SubmissionError(f'Source does not exist: {source}')
    remaining = [item for item in metadata if item is not entry]

    # Older submissions can use their original name, stored name, or numeric ID.
    submissions = {Path('submissions') / filename,
                   Path('submissions') / f'{identifier}.svg'}
    original = entry.get('Submission')
    if original is not None:
        if (not isinstance(original, str)
                or re.fullmatch(r'submissions/[^/\\\x00-\x1f]+\.svg', original) is None):
            raise SubmissionError('Invalid Submission path in metadata.')
        submissions.add(Path(original))
    shared_submissions = {
        value for item in remaining
        for value in (item.get('Submission'),
                      f"submissions/{item.get('Source', '')}",
                      f"submissions/{item['Id']}.svg")
        if isinstance(value, str)
    }
    targets = {source, Path('previews') / f'{identifier}.png'}
    targets.update(path for path in submissions
                   if path.as_posix() not in shared_submissions)

    # Legacy generated filenames end with the icon ID. A digit boundary avoids
    # matching another icon whose longer ID merely has the same suffix.
    for directory, suffix in [('xml', '.xml'), ('pack', '.kt')]:
        root = Path(directory)
        if root.is_symlink():
            raise SubmissionError(f'Refusing symlink: {root}')
        if root.exists() and not root.is_dir():
            raise SubmissionError(f'Expected a directory: {root}')
        for path in root.glob(f'*{suffix}'):
            if re.search(rf'(?<![0-9]){re.escape(identifier)}$', path.stem):
                targets.add(path)

    # Validate the entire removal set before changing any files.
    for path in targets:
        validate_path(path)
    updated_metadata = json.dumps(remaining, indent=2, ensure_ascii=False) + '\n'
    for path in sorted(targets):
        if path.exists():
            path.unlink()
            print(f'Removed {path}')
    metadata_path.write_text(updated_metadata, encoding='utf-8')
    print(f'Removed metadata entry {identifier} ({filename}).')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True, help='Filename under svg/, optionally without .svg')
    args = parser.parse_args()
    try:
        remove_icon_pack(args.name)
    except (SubmissionError, OSError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
