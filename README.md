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

- Adapted for both PC and Mac
- Parse XML files with customizable extraction rules
- Export data to CSV and Excel formats
- Configurable tag extraction with sign control (positive/negative)
- Output column ordering, renaming, hiding, and merging
- Control sums to verify no data was lost or duplicated during parsing
- Support for multiple named configs (CAMT, custom)
- Modern GUI with tabbed interface
- Window size and position remembered across sessions

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

**Important**: This software is provided "as is", without warranty of any kind. The authors and contributors take no responsibility or liability for the accuracy, correctness, or completeness of the parsed data. Users should independently verify any critical data exported by this tool.

## License

MIT License — Copyright (c) 2026 opheophe@gmail.com

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
