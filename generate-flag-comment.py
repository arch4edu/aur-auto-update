#!/usr/bin/env python3
"""
Generate standardized AUR flag comment from a GitHub Actions run ID.

Usage: generate-flag-comment.py <run-id>

Extracts package name and new version from the run's display title.
Fetches current version from AUR RPC and checks log for dependency issues.
"""

import subprocess
import json
import urllib.request
import re
import sys


def get_github_run_metadata(run_id: str) -> dict:
    """Get GitHub Actions run metadata (displayTitle, url)."""
    try:
        result = subprocess.run(
            ['gh', 'run', 'view', str(run_id), '--json', 'displayTitle,url'],
            capture_output=True, text=True, check=True, timeout=30
        )
        data = json.loads(result.stdout)
        return {
            'display_title': data.get('displayTitle', ''),
            'url': data.get('url', f'https://github.com/arch4edu/aur-auto-update/actions/runs/{run_id}')
        }
    except subprocess.CalledProcessError as e:
        return {'error': f'gh command failed: {e.stderr}'}
    except Exception as e:
        return {'error': str(e)}


def parse_display_title(title: str) -> tuple:
    """
    Parse package name and new version from display title.
    
    Expected formats:
        "Build test for twitch-dl 3.3.1"
        "Build test for netron 8.9.0"
        "nvchecker: update to x.y.z"
    Returns (package, newver) or (None, None).
    """
    if not title:
        return None, None
    
    # Pattern: "Build test for <package> <version>" or "nvchecker: update to <package> <version>"
    m = re.search(r'(?:Build test for|nvchecker:?)\s+([a-zA-Z0-9_-]+)\s+([\d.]+)', title)
    if m:
        return m.group(1), m.group(2)
    
    # Fallback: last word is version
    parts = title.split()
    if len(parts) >= 2:
        potential_ver = parts[-1]
        if re.match(r'^\d+(\.\d+)*[a-zA-Z0-9-]*$', potential_ver):
            package = ' '.join(parts[:-1])
            # Clean package name
            package = re.sub(r'^.*for\s+', '', package).strip()
            return package, potential_ver
    
    return None, None


def get_aur_current_version(package: str) -> str:
    """Fetch current version from AUR RPC."""
    try:
        url = f"https://aur.archlinux.org/rpc/?v=5&type=info&arg[]={urllib.request.quote(package)}"
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode())
            if data.get('resultcount', 0) > 0:
                pkg_info = data['results'][0]
                return pkg_info.get('Version', 'unknown')
    except Exception:
        pass
    return 'unknown'


def get_run_dependency_info(run_id: str) -> dict:
    """Check run log for dependency resolution errors."""
    try:
        result = subprocess.run(
            ['gh', 'run', 'view', str(run_id), '--log'],
            capture_output=True, text=True, check=True, timeout=30
        )
        log = result.stdout
        
        has_dep_error = False
        missing_dep = None
        
        for line in log.split('\n'):
            if '==> ERROR:' in line:
                error_text = line.split('==> ERROR:')[1].strip().lower()
                if 'failed to install missing dependencies' in error_text or 'could not resolve all dependencies' in error_text:
                    has_dep_error = True
        
        if has_dep_error:
            for line in log.split('\n'):
                if 'target not found:' in line:
                    missing_dep = line.split('target not found:')[1].strip()
                    break
        
        return {'has_dependency_error': has_dep_error, 'missing_dependency': missing_dep}
    except subprocess.CalledProcessError as e:
        return {'error': f'gh command failed: {e.stderr}'}
    except Exception as e:
        return {'error': str(e)}


def generate_flag_comment(package: str, oldver: str, newver: str, run_id: str, missing_dep: str = None) -> str:
    """Generate standardized AUR flag comment."""
    lines = [
        f"New version {newver} is available.",
        f"Current version {oldver} is outdated."
    ]
    
    if missing_dep:
        lines.append("")
        lines.append(f"The build test fails because of missing dependencies: {missing_dep}.")
        lines.append(f"If there's a repository providing these dependencies, you can create a {package}.repository file.")
    
    ci_url = f"https://github.com/arch4edu/aur-auto-update/actions/runs/{run_id}"
    lines.append("")
    lines.append(f"See: {ci_url}")
    
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: generate-flag-comment.py <run-id>")
        print("Example: generate-flag-comment.py 22032164368")
        return 1
    
    run_id = sys.argv[1]
    
    # Get run metadata
    metadata = get_github_run_metadata(run_id)
    if 'error' in metadata:
        print(f"Error: {metadata['error']}")
        return 1
    
    display_title = metadata.get('display_title', '')
    package, newver = parse_display_title(display_title)
    
    if not package:
        print(f"Error: Could not extract package name from run title: '{display_title}'")
        return 1
    
    if not newver:
        print(f"Error: Could not extract new version from run title: '{display_title}'")
        return 1
    
    # Get current version from AUR
    oldver = get_aur_current_version(package)
    
    # Check for dependency issues
    dep_info = get_run_dependency_info(run_id)
    missing_dep = None
    if dep_info.get('has_dependency_error'):
        missing_dep = dep_info.get('missing_dependency')
    
    # Generate and output comment
    comment = generate_flag_comment(package, oldver, newver, run_id, missing_dep)
    print(comment)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
