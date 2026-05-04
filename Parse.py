import xml.etree.ElementTree as ET


def strip_namespaces(elem):
    """Recursively strip namespaces from XML element and its children"""
    if '}' in elem.tag:
        elem.tag = elem.tag.split('}')[-1]
    
    for key in list(elem.attrib.keys()):
        if '}' in key:
            new_key = key.split('}')[-1]
            elem.attrib[new_key] = elem.attrib[key]
            del elem.attrib[key]
    
    for child in elem:
        strip_namespaces(child)
    
    return elem


def get_leaf_nodes(elem, path="", leaves=None):
    """Get all leaf nodes (elements with no children)"""
    if leaves is None:
        leaves = []
    
    current_path = f"{path}/{elem.tag}" if path else elem.tag
    
    # Check if leaf (no children)
    if len(elem) == 0:
        text = elem.text.strip() if elem.text else ""
        attrs = dict(elem.attrib)
        leaves.append({
            'path': current_path,
            'tag': elem.tag,
            'text': text,
            'attributes': attrs
        })
    else:
        # Recurse into children
        for child in elem:
            get_leaf_nodes(child, current_path, leaves)
    
    return leaves


def main():
    file_path = "Testdata/indata.XML"
    
    # Parse XML
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Strip namespaces
    root = strip_namespaces(root)
    
    # Get all leaf nodes
    leaves = get_leaf_nodes(root)
    
    # Get unique column headers (paths)
    columns = sorted(set(leaf['path'] for leaf in leaves))
    
    # Print column headers
    print(f"Found {len(columns)} unique column headers:\n")
    print("=" * 80)
    for i, col in enumerate(columns, 1):
        print(f"{i:3}. {col}")
    print("=" * 80)
    
    # Also print all leaf nodes with values
    print(f"\n\nFound {len(leaves)} leaf nodes:\n")
    print("-" * 80)
    
    for leaf in leaves:
        attr_str = ""
        if leaf['attributes']:
            attr_str = " " + " ".join([f"{k}=\"{v}\"" for k, v in leaf['attributes'].items()])
        
        print(f"Path: {leaf['path']}")
        print(f"Tag: <{leaf['tag']}{attr_str}>")
        print(f"Text: {leaf['text']!r}")
        print("-" * 80)


def build_csv_rows(leaves, record_path_segment="Ntry"):
    """Build CSV rows where parent data is repeated for each record"""
    
    # Group leaves by their record (Ntry)
    records = {}
    for leaf in leaves:
        path = leaf['path']
        # Find which record this leaf belongs to
        parts = path.split('/')
        if record_path_segment in parts:
            # Find the record ID based on position of record_path_segment
            idx = parts.index(record_path_segment)
            # Record key is the full path up to and including the record index
            # We need to distinguish between multiple records
            record_key = '/'.join(parts[:idx+1])
            
            if record_key not in records:
                records[record_key] = {}
            
            # Store the leaf data with the column path relative to record
            column_path = path
            records[record_key][column_path] = {
                'text': leaf['text'],
                'attributes': leaf['attributes']
            }
    
    return records


def flatten_to_csv(leaves, output_file):
    """Convert leaves to CSV, repeating parent data for each record"""
    
    # Find all unique column paths and identify amount fields
    raw_columns = sorted(set(leaf['path'] for leaf in leaves))
    
    # Build expanded columns list - split amount fields into value and currency
    all_columns = []
    amount_columns = set()  # Track which columns are amount fields
    for col in raw_columns:
        if col.endswith('/Amt') or col.endswith('/RmtdAmt'):
            # Split into value and currency columns
            all_columns.append(f"{col}@Value")
            all_columns.append(f"{col}@Ccy")
            amount_columns.add(col)
        else:
            all_columns.append(col)
    
    # Group data by record (each Ntry is a row)
    from collections import Counter
    path_counts = Counter(leaf['path'] for leaf in leaves)
    
    # The repeating path with highest count indicates number of records
    max_count = max(path_counts.values())
    num_records = max_count
    print(f"Detected {num_records} records")
    
    # Assign each leaf to a record based on its occurrence index
    occurrence_counters = {}
    record_data = [{} for _ in range(num_records)]
    
    for leaf in leaves:
        path = leaf['path']
        if path not in occurrence_counters:
            occurrence_counters[path] = 0
        
        record_idx = occurrence_counters[path]
        occurrence_counters[path] += 1
        
        # Get text value
        value = leaf['text']
        
        # Check if this is an amount field with currency attribute
        if path in amount_columns:
            # Get currency from attributes
            currency = leaf['attributes'].get('Ccy', '')
            # Store in separate columns
            record_data[record_idx][f"{path}@Value"] = value
            record_data[record_idx][f"{path}@Ccy"] = currency
        else:
            # For non-amount fields, combine text and any other attributes
            if leaf['attributes']:
                attr_parts = [f"{k}={v}" for k, v in leaf['attributes'].items()]
                value = f"{value} ({' '.join(attr_parts)})" if value else ' '.join(attr_parts)
            record_data[record_idx][path] = value
    
    # Write CSV
    import csv
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_columns)
        writer.writeheader()
        writer.writerows(record_data)
    
    return num_records, len(all_columns)


def main():
    file_path = "Testdata/indata.XML"
    output_file = "Testdata/output.csv"
    
    # Parse XML
    tree = ET.parse(file_path)
    root = tree.getroot()
    
    # Strip namespaces
    root = strip_namespaces(root)
    
    # Get all leaf nodes
    leaves = get_leaf_nodes(root)
    
    # Get unique column headers (paths)
    columns = sorted(set(leaf['path'] for leaf in leaves))
    
    # Print column headers
    print(f"Found {len(columns)} unique column headers:\n")
    print("=" * 80)
    for i, col in enumerate(columns, 1):
        print(f"{i:3}. {col}")
    print("=" * 80)
    
    # Create CSV
    print(f"\nCreating CSV file: {output_file}")
    num_records, num_cols = flatten_to_csv(leaves, output_file)
    print(f"✓ Wrote {num_records} rows with {num_cols} columns to {output_file}")


if __name__ == "__main__":
    main()
