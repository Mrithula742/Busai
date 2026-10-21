"""Read-only SUNT inventory. File stats first; optional Parquet footer inspection."""
import argparse
from collections import defaultdict
import csv
import json
from pathlib import Path


def inventory(root, output, schemas=False):
    root, output = Path(root), Path(output)
    if not root.is_dir():
        raise ValueError(f'Extracted SUNT directory not found: {root}')
    output.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list)
    with (output/'file_inventory.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=['path', 'bytes', 'format'])
        writer.writeheader()
        for path in sorted(root.rglob('*')):
            if not path.is_file():
                continue
            record = {'path': str(path.relative_to(root)), 'bytes': path.stat().st_size, 'format': path.suffix}
            writer.writerow(record)
            groups[str(path.parent.relative_to(root))].append(record)
    summary = {'source': str(root), 'directories': {
        name: {'files': len(rows), 'bytes': sum(row['bytes'] for row in rows)} for name, rows in groups.items()}}
    if schemas:
        import pyarrow.parquet as pq
        examples = {}
        for directory, pattern in [('AVL', 'avl-vehicles-*.parquet'), ('AVL', 'avl-lines-*.parquet'), ('AFC', '*.parquet')]:
            path = next(iter(sorted((root/directory).glob(pattern))), None)
            if path:
                parquet = pq.ParquetFile(path)
                examples[str(path.relative_to(root))] = {
                    'bytes': path.stat().st_size, 'rows': parquet.metadata.num_rows,
                    'row_groups': parquet.metadata.num_row_groups,
                    'schema': str(parquet.schema_arrow)}
        summary['representative_parquet_metadata'] = examples
    (output/'inventory.json').write_text(json.dumps(summary, indent=2)+'\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--schemas', action='store_true')
    args = parser.parse_args()
    print(json.dumps(inventory(args.source, args.output, args.schemas), indent=2))
