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

## License

[Add your license information here]
