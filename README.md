# windows-evaluation-iso-download-scraper

Scrapes up-to-date download URLs and SHA256 checksums for Windows Evaluation ISOs from [Microsoft's Evaluation Center](https://www.microsoft.com/en-us/evalcenter).

## Scraped ISOs

| Output                                     | ISO                            |
| ------------------------------------------ | ------------------------------ |
| `data/windows-11-enterprise.json`          | Windows 11 Enterprise          |
| `data/windows-11-enterprise-ltsc.json`     | Windows 11 Enterprise LTSC     |
| `data/windows-11-iot-enterprise-ltsc.json` | Windows 11 IoT Enterprise LTSC |
| `data/windows-2022.json`                   | Windows Server 2022            |
| `data/windows-2025.json`                   | Windows Server 2025            |

## Output format

```json
{
  "name": "windows-2025",
  "url": "https://software-static.download.prss.microsoft.com/...iso",
  "fwlink": "https://go.microsoft.com/fwlink/?linkid=...",
  "sha256": "abc123...",
  "size": 5368709120,
  "scraped_at": "2026-03-31T00:00:00Z"
}
```

## Usage

```sh
# Scrape all targets
python3 scrape.py

# Scrape specific targets
python3 scrape.py windows-2025 windows-2022
```

## See also

Inspired by [rgl/windows-evaluation-isos-scraper](https://github.com/rgl/windows-evaluation-isos-scraper), which additionally extracts WIM image metadata (edition names, build versions, ...) by downloading and mounting ISOs on a Windows runner using PowerShell.

## Automation

A GitHub Actions workflow runs every Wednesday at midnight UTC, commits any updated `data/*.json` files, and pushes to the repository.
