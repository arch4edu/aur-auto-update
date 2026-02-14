#!/usr/bin/env python3

import subprocess
import json
import urllib.request
from datetime import datetime, timezone
from typing import List, Dict

def run_gh_command(args: List[str]) -> str:
    result = subprocess.run(['gh'] + args, capture_output=True, text=True, check=True)
    return result.stdout

def get_check_update_time() -> tuple[datetime, str]:
    print("🔍 Getting last check update action time...")
    try:
        output = run_gh_command(['run', 'list', '--workflow=check-update.yml', '--limit=1', '--json=databaseId,createdAt'])
        runs = json.loads(output)
        if not runs:
            raise Exception("No check-update workflow runs found")
        run = runs[0]
        run_id = run['databaseId']
        created_at = run['createdAt']
        check_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        print(f"   Last check update time: {check_time.isoformat()} (run_id: {run_id})")
        return check_time, run_id
    except subprocess.CalledProcessError as e:
        print(f"  gh command failed: {e.stderr}")
        raise
    except Exception as e:
        print(f"  Error: {e}")
        raise

def get_build_test_runs_since(check_time: datetime) -> List[Dict]:
    print(f"🔍 Finding build test runs since {check_time.isoformat()}...")
    try:
        output = run_gh_command(['run', 'list', '--workflow=build.yml', '--limit=50', '--json=databaseId,displayTitle,createdAt,status,conclusion'])
        runs = json.loads(output)
        recent_runs = []
        for run in runs:
            created_at = datetime.fromisoformat(run['createdAt'].replace('Z', '+00:00'))
            if created_at > check_time:
                run['createdAt_dt'] = created_at
                recent_runs.append(run)
        print(f"   Found {len(recent_runs)} build test runs after specified time")
        return recent_runs
    except subprocess.CalledProcessError as e:
        print(f"  gh command failed: {e.stderr}")
        return []
    except Exception as e:
        print(f"  Error: {e}")
        return []

def extract_package_name(title: str) -> str:
    if title.startswith('Build test for '):
        parts = title[15:].split(' ', 1)
        return parts[0] if parts else ""
    return ""

def query_aur_packages(package_names: List[str]) -> Dict[str, tuple]:
    if not package_names:
        return {}
    print(f"🌐 Querying AUR for {len(package_names)} packages last update time and maintainer info...")
    query_parts = ["v=5", "type=info"]
    for pkg in package_names:
        query_parts.append(f"arg[]={urllib.request.quote(pkg)}")
    url = f"https://aur.archlinux.org/rpc/?{'&'.join(query_parts)}"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode())
            aur_info = {}
            bot_identifiers = ['AutoUpdateBot', 'auto-update-bot@arch4edu.org', 'arch4edu']
            for pkg_info in data.get('results', []):
                name = pkg_info.get('Name')
                last_modified = pkg_info.get('LastModified')
                maintainer = pkg_info.get('Maintainer', '')
                comaintainers = pkg_info.get('CoMaintainers', [])
                if name and last_modified:
                    is_co_maintainer = False
                    all_maintainers = [maintainer] + comaintainers
                    for maint in all_maintainers:
                        for bot_id in bot_identifiers:
                            if bot_id in maint:
                                is_co_maintainer = True
                                break
                        if is_co_maintainer:
                            break
                    aur_info[name] = (
                        datetime.fromtimestamp(last_modified, tz=timezone.utc),
                        is_co_maintainer
                    )
            print(f"   Successfully retrieved AUR info for {len(aur_info)}/{len(package_names)} packages")
            return aur_info
    except Exception as e:
        print(f"  AUR query failed: {e}")
        return {}

def get_error_message(run_id: str) -> str:
    try:
        output = run_gh_command(['run', 'view', str(run_id), '--log'])
        error_lines = []
        for line in output.split('\n'):
            if '==> ERROR:' in line:
                error_text = line.split('==> ERROR:')[1].strip()
                if error_text:
                    error_lines.append(error_text)
            elif 'is greater than newver' in line:
                error_text = line.strip()
                if error_text:
                    error_lines.append(error_text)
        if error_lines:
            return '; '.join(error_lines[:2])
        return "No==>ERRORerrors"
    except Exception as e:
        return f"Failed to get log: {str(e)}"

def process_builds(build_runs: List[Dict], aur_info: Dict[str, tuple], check_time: datetime):
    print("\n" + "="*120)
    print("📊 AUR Auto-Update Build Results")
    print("="*120)
    print(f"{'Package':<40} {'Run ID':<12} {'AURUpdate':<20} {'Status':<20}")
    print("-"*120)
    total = len(build_runs)
    success_count = 0
    fail_count = 0
    aur_not_updated_count = 0
    not_maintained_count = 0
    downgrade_count = 0
    for build in build_runs:
        pkg = build['package']
        run_id = build['run_id']
        aur_data = aur_info.get(pkg)
        if aur_data:
            aur_time, is_co_maintainer = aur_data
            aur_time_str = aur_time.strftime('%Y-%m-%d %H:%M')
        else:
            aur_time_str = "Unknown"
            is_co_maintainer = False
        if not is_co_maintainer:
            status = "⚫ No longer maintained"
            not_maintained_count += 1
            fail_count += 1
        else:
            error_msg = get_error_message(run_id)
            build_failed = error_msg != "No==>ERRORerrors"
            downgrade_rejected = "greater than newver" in error_msg.lower()
            if downgrade_rejected:
                status = "⚠️ Upgrade failed (downgrade)"
                downgrade_count += 1
                fail_count += 1
            elif build_failed:
                status = "❌ Build failed"
                fail_count += 1
            else:
                aur_success = aur_time and aur_time > check_time
                if aur_success:
                    status = "✅ Fully successful"
                    success_count += 1
                elif aur_time:
                    status = "🟡 Not updated on AUR"
                    aur_not_updated_count += 1
                else:
                    status = "⚪ No AUR data"
                    fail_count += 1
        display_name = pkg if len(pkg) <= 38 else pkg[:35] + "..."
        print(f"{display_name:<40} {run_id:<12} {aur_time_str:<20} {status:<20}")
    print("="*120)
    print(f"Total: {total} packages")
    print(f"  ✅ Fully successful: {success_count}")
    print(f"  ❌ Build failed: {fail_count}")
    print(f"  🟡 Not updated on AUR: {aur_not_updated_count}")
    print(f"  ⚫ No longer maintained: {not_maintained_count}")
    print(f"  ⚠️  Upgrade failed (downgrade): {downgrade_count}")
    print("="*120)

def main():
    try:
        print("=" * 60)
        print("🚀 AUR Auto-Update Actions Analysis Script")
        print("=" * 60)
        check_time, check_run_id = get_check_update_time()
        recent_build_runs = get_build_test_runs_since(check_time)
        if not recent_build_runs:
            print("⚠️  No build test runs found after check update")
            return
        print("\n🔧 Analyzing build test runs...")
        build_data = []
        package_names = []
        for run in recent_build_runs:
            run_id = run['databaseId']
            title = run.get('displayTitle', '')
            conclusion = run.get('conclusion')
            pkg = extract_package_name(title)
            if pkg and conclusion:
                build_data.append({
                    'run_id': run_id,
                    'package': pkg,
                    'conclusion': conclusion,
                })
                if pkg not in package_names:
                    package_names.append(pkg)
        if not build_data:
            print("⚠️  Could not extract valid package names from build test runs")
            return
        print(f"   Extracted {len(build_data)} build records for {len(package_names)} unique packages")
        
        # Sort by package name for consistent output
        build_data.sort(key=lambda x: x['package'])
        
        aur_info = query_aur_packages(package_names)
        process_builds(build_data, aur_info, check_time)
    except Exception as e:
        print(f"\n❌ Script execution failed: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == '__main__':
    main()
