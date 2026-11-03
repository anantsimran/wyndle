"""Build the standalone Reading Desk VSIX with Python's standard library."""

import json
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


def package() -> Path:
    root = Path(__file__).resolve().parent
    metadata = json.loads((root / "package.json").read_text(encoding="utf-8"))
    name, version = metadata["name"], metadata["version"]
    output = root / "dist" / f"{name}-{version}.vsix"
    output.parent.mkdir(exist_ok=True)
    manifest = f'''<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011">
  <Metadata>
    <Identity Language="en-US" Id="{name}" Version="{version}" Publisher="{metadata['publisher']}" />
    <DisplayName>{escape(metadata['displayName'])}</DisplayName>
    <Description xml:space="preserve">{escape(metadata['description'])}</Description>
    <Categories>Other</Categories>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{metadata['engines']['vscode']}" />
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace" />
      <Property Id="Microsoft.VisualStudio.Code.ExecutesCode" Value="true" />
    </Properties>
  </Metadata>
  <Installation><InstallationTarget Id="Microsoft.VisualStudio.Code" /></Installation>
  <Dependencies />
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Content.Details" Path="extension/README.md" Addressable="true" />
    <Asset Type="Microsoft.VisualStudio.Services.Content.License" Path="extension/LICENSE" Addressable="true" />
  </Assets>
</PackageManifest>'''
    content_types = '''<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="json" ContentType="application/json" />
  <Default Extension="js" ContentType="application/javascript" />
  <Default Extension="css" ContentType="text/css" />
  <Default Extension="svg" ContentType="image/svg+xml" />
  <Default Extension="md" ContentType="text/markdown" />
  <Default Extension="vsixmanifest" ContentType="text/xml" />
  <Override PartName="/extension/LICENSE" ContentType="text/plain" />
</Types>'''
    files = ["package.json", "extension.js", "anchors.js", "store.js", "README.md", "REQUIREMENTS.md", "LICENSE",
             "media/book.svg", "media/reader.css", "media/preview.css", "media/preview.js"]
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("extension.vsixmanifest", manifest)
        archive.writestr("[Content_Types].xml", content_types)
        for filename in files:
            archive.write(root / filename, f"extension/{filename}")
    return output


if __name__ == "__main__":
    print(package())
