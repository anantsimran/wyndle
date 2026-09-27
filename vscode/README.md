# Wyndle — The Next Step

A calm, Stormlight-inspired focus dashboard beside your code. Add a small task,
start a focus block, take a break, and leave tomorrow an easy first step.

Install the Python package from the repository first (`uv sync`). In
VS Code settings, set `wyndle.executable` to its full installed path. Open the
Wyndle activity-bar view; it starts or reuses the local server on port 8765.

The same dashboard is available in your browser through **Wyndle: Open in Browser**.
Tasks and times are shared with the CLI and stored locally as Markdown and state
files. The backend server started by this extension stops when the extension
closes; manually started servers keep running.

For development, open the repository root, press F5, and choose **Run Wyndle Extension**.
For local installation, run `npm run package`, then install the resulting VSIX.
See the root README’s **How to run** section for full instructions.

Local desktop VS Code only. Unofficial literary inspiration; no affiliation with
Brandon Sanderson. No telemetry or runtime npm dependencies.
