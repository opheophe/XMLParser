# XMLParser

A Python-based XML parsing application with GUI for extracting and exporting XML data to CSV and Excel formats.

## Installation

### From GitHub Releases

1. Download the appropriate file for your system:
   - **Windows**: `XMLParser.exe`
   - **macOS**: `XMLParser_Mac_Intel.dmg` (Intel Macs) or `XMLParser_Mac_Silicon.dmg` (Apple Silicon)

### macOS Installation Instructions

**Important**: Due to macOS security requirements, you may need to:

1. **First time opening**:
   - Right-click the app and select "Open"
   - Click "Open" in the security dialog
   - Or go to System Settings → Privacy & Security → Allow Anyway

2. **Alternative method**:
   ```
   sudo xattr -rd com.apple.quarantine /Applications/XMLParser.app
   ```

This is normal for apps not distributed through the App Store and ensures your security.

## Features

- Parse XML files with customizable extraction rules
- Export data to CSV and Excel formats
- Configurable tag extraction and column merging
- Support for multiple XML formats (CAMT, custom configs)
- Modern GUI with tabbed interface

## Development

### Requirements

- Python 3.11+
- Required packages: `pandas`, `openpyxl`, `tkinter` (included with Python)

### Building from Source

```bash
# Install dependencies
pip install -r requirements.txt

# Build executable
pyinstaller --onefile --windowed --icon=icon.icns XMLParser.py
```

## Disclaimer
Important: This software is provided "as is", without warranty of any kind. The authors and contributors take no responsibility or liability for the accuracy, correctness, or completeness of the parsed data. Users should independently verify any critical data exported by this tool.

## License

## License

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.
