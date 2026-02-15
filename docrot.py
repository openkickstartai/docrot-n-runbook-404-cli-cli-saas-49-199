#!/usr/bin/env python3
"""DocRot - Documentation Rot Detection Engine. Zero-dependency CLI."""
import argparse, json, re, sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List
from urllib.request import urlopen, Request


@dataclass
class Issue:
    file: str; line: int; kind: str; message: str; severity: str = "warning"


@dataclass
class ScanResult:
    issues: List[Issue] = field(default_factory=list); docs_scanned: int = 0


LINK_RE = re.compile(r'\[([^\]]*)\]\(([^)]+)\)')
CODE_BLOCK_RE = re.compile(r'```\w*\n(.*?)```', re.DOTALL)
IMPORT_RE = re.compile(r'(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))')


def _url_ok(url):
    try:
        urlopen(Request(url, method='HEAD', headers={'User-Agent': 'DocRot/0.1'}), timeout=5)
        return True
    except Exception:
        return False


def _mod_exists(root, mod):
    mp = mod.replace('.', '/')
    return any((root / f).exists() for f in [f"{mp}.py", f"{mp}.go", f"{mp}.ts", f"{mp}.rs", mp])


def scan_doc(doc_path, root, check_urls=False):
    issues, text = [], Path(doc_path).read_text(errors='replace')
    rel, in_block = str(Path(doc_path).relative_to(root)), False
    root = Path(root)
    for i, line in enumerate(text.split('\n'), 1):
        if line.startswith('```'):
            in_block = not in_block
            continue
        if in_block:
            continue
        for m in LINK_RE.finditer(line):
            href = m.group(2)
            target = href.split('#')[0].split('?')[0]
            if href.startswith(('http://', 'https://')):
                if check_urls and not _url_ok(href):
                    issues.append(Issue(rel, i, "dead_url", f"URL error: {href}"))
            elif not href.startswith(('mailto:', '#')):
                if target and not (Path(doc_path).parent / target).resolve().exists():
                    if not (root / target).exists():
                        issues.append(Issue(rel, i, "broken_link", f"Broken link: {target}"))
        for m in IMPORT_RE.finditer(line):
            mod = m.group(1) or m.group(2)
            if mod and not _mod_exists(root, mod):
                issues.append(Issue(rel, i, "stale_symbol", f"Module not found: {mod}"))
    for m in CODE_BLOCK_RE.finditer(text):
        ln = text[:m.start()].count('\n') + 2
        for im in IMPORT_RE.finditer(m.group(1)):
            mod = im.group(1) or im.group(2)
            if mod and not _mod_exists(root, mod):
                issues.append(Issue(rel, ln, "code_drift", f"Code block refs missing: {mod}"))
    return issues


def scan_repo(root, check_urls=False, max_docs=0):
    result, root = ScanResult(), Path(root).resolve()
    for pat in ('**/*.md', '**/*.rst', '**/*.adoc'):
        for doc in sorted(root.glob(pat)):
            if any(p in doc.parts for p in ('.git', 'node_modules', '__pycache__')):
                continue
            if 0 < max_docs <= result.docs_scanned:
                break
            result.issues.extend(scan_doc(doc, root, check_urls))
            result.docs_scanned += 1
    return result


def to_sarif(r):
    rules = list({i.kind for i in r.issues})
    return {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "DocRot",
        "version": "0.1.0", "rules": [{"id": k, "shortDescription": {"text": k}} for k in rules]}},
        "results": [{"ruleId": i.kind, "level": "warning", "message": {"text": i.message},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": i.file},
        "region": {"startLine": i.line}}}]} for i in r.issues]}]}


def fmt(r, style="text"):
    if style == "json":
        return json.dumps({"docs_scanned": r.docs_scanned, "total_issues": len(r.issues),
            "issues": [asdict(i) for i in r.issues]}, indent=2)
    if style == "sarif":
        return json.dumps(to_sarif(r), indent=2)
    if not r.issues:
        return f"\u2705 Scanned {r.docs_scanned} docs \u2014 no rot detected!"
    icons = {"broken_link": "\U0001f517", "stale_symbol": "\U0001f3f7\ufe0f",
             "code_drift": "\U0001f4dd", "dead_url": "\U0001f310"}
    out = [f"\n\U0001f9b7 DocRot Report \u2014 {len(r.issues)} issues in {r.docs_scanned} docs",
           "\u2500" * 50]
    for i in r.issues:
        out.append(f"  {icons.get(i.kind, '\u26a0\ufe0f')}  {i.file}:{i.line}  [{i.kind}] {i.message}")
    out += ["\u2500" * 50, "\U0001f4a1 Upgrade for cross-repo scanning: https://docrot.dev"]
    return '\n'.join(out)


def main(argv=None):
    p = argparse.ArgumentParser(prog="docrot", description="Detect rotting documentation")
    p.add_argument("path", nargs="?", default=".", help="Repo root to scan")
    p.add_argument("-f", "--format", choices=["text", "json", "sarif"], default="text")
    p.add_argument("--check-urls", action="store_true", help="Check external URLs (Team+)")
    p.add_argument("--max-docs", type=int, default=50, help="Max docs (free=50)")
    a = p.parse_args(argv)
    root = Path(a.path).resolve()
    if not root.is_dir():
        print(f"Error: {root} is not a directory", file=sys.stderr)
        sys.exit(2)
    result = scan_repo(root, a.check_urls, a.max_docs)
    print(fmt(result, a.format))
    sys.exit(1 if result.issues else 0)


if __name__ == "__main__":
    main()


# --- CLI Command/Flag Staleness Detection ---

SHELL_LANGS = {'bash', 'shell', 'sh', 'console', 'zsh'}
CLI_FLAG_RE = re.compile(r'(--[a-zA-Z][\w-]*|-[a-zA-Z])\b')
FENCE_LANG_RE = re.compile(r'^```(\w*)')


def _parse_yaml_list(s):
    """Parse a YAML inline list like [--flag1, --flag2]."""
    s = s.strip()
    if s.startswith('[') and s.endswith(']'):
        return [item.strip() for item in s[1:-1].split(',') if item.strip()]
    return []


def _parse_cli_config(config_path):
    """Minimal YAML parser for .docrot-cli.yml (no PyYAML dependency)."""
    text = Path(config_path).read_text(errors='replace')
    commands = {}
    current_cmd = None
    cmd_indent = 0
    in_commands = False
    commands_indent = -1

    for line in text.split('\n'):
        if not line.strip() or line.strip().startswith('#'):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        if stripped == 'commands:':
            in_commands = True
            commands_indent = indent
            continue

        if not in_commands:
            continue

        if indent <= commands_indent:
            break

        if stripped.endswith(':') and not stripped.startswith(('flags:', 'deprecated:')):
            current_cmd = stripped[:-1].strip()
            cmd_indent = indent
            commands[current_cmd] = {'flags': [], 'deprecated': []}
            continue

        if current_cmd is not None and indent > cmd_indent:
            if stripped.startswith('flags:'):
                commands[current_cmd]['flags'] = _parse_yaml_list(
                    stripped[len('flags:'):])
            elif stripped.startswith('deprecated:'):
                commands[current_cmd]['deprecated'] = _parse_yaml_list(
                    stripped[len('deprecated:'):])

    return commands


class CliCommandDetector:
    """Detect stale/unknown/deprecated CLI flags in Markdown documentation."""

    def __init__(self, root):
        self.root = Path(root)
        self.commands = None
        config_path = self.root / '.docrot-cli.yml'
        if config_path.exists():
            self.commands = _parse_cli_config(config_path)

    def detect(self, doc_path, text=None):
        """Scan a document for CLI flag issues. Returns list of Issue."""
        if self.commands is None:
            return []
        if text is None:
            text = Path(doc_path).read_text(errors='replace')
        try:
            rel = str(Path(doc_path).relative_to(self.root))
        except ValueError:
            rel = str(doc_path)

        issues = []
        in_block = False
        block_lang = ''
        block_lines = []

        for i, line in enumerate(text.split('\n'), 1):
            if line.startswith('```'):
                if in_block:
                    if self._is_shell_block(block_lang, block_lines):
                        issues.extend(self._check_block(rel, block_lines))
                    in_block = False
                    block_lines = []
                    block_lang = ''
                else:
                    in_block = True
                    m = FENCE_LANG_RE.match(line)
                    block_lang = m.group(1) if m else ''
                    block_lines = []
            elif in_block:
                block_lines.append((i, line))
        return issues

    def _is_shell_block(self, lang, lines):
        """Determine if a code block is a shell block."""
        if lang.lower() in SHELL_LANGS:
            return True
        if lang == '':
            return any(
                ln.strip().startswith('$') or ln.strip().startswith('>')
                for _, ln in lines
            )
        return False

    def _check_block(self, rel, lines):
        """Check all lines in a shell block for flag issues."""
        issues = []
        for line_no, content in lines:
            cmd_line = re.sub(r'^\s*[$>]\s*', '', content).strip()
            if not cmd_line or cmd_line.startswith('#'):
                continue
            # Split on pipes and logical operators to avoid false positives
            for segment in re.split(r'\|{1,2}|&&|;', cmd_line):
                segment = segment.strip()
                if not segment:
                    continue
                parts = segment.split()
                cmd_name = parts[0].split('/')[-1] if parts else None
                if cmd_name not in self.commands:
                    continue
                cfg = self.commands[cmd_name]
                valid = set(cfg.get('flags', []))
                deprecated = set(cfg.get('deprecated', []))
                for fm in CLI_FLAG_RE.finditer(segment):
                    flag = fm.group(1)
                    if flag in deprecated:
                        issues.append(Issue(
                            rel, line_no, "CLI_FLAG_DEPRECATED",
                            f"Deprecated CLI flag '{flag}' for command '{cmd_name}'"))
                    elif flag not in valid:
                        issues.append(Issue(
                            rel, line_no, "CLI_FLAG_UNKNOWN",
                            f"Unknown CLI flag '{flag}' for command '{cmd_name}'"))
        return issues


def detect_cli_issues(doc_path, root):
    """Convenience function: detect CLI flag issues in a single document."""
    return CliCommandDetector(root).detect(doc_path)
