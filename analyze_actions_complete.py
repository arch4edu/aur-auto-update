#!/usr/bin/env python3

import subprocess
import json
import os
import re
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
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.loads(response.read().decode())
        aur_info = {}
        bot_identifiers = ['AutoUpdateBot', 'auto-update-bot@arch4edu.org', 'arch4edu']
        for pkg_info in data.get('results', []):
            name = pkg_info.get('Name')
            last_modified = pkg_info.get('LastModified')
            maintainer = pkg_info.get('Maintainer') or ''
            comaintainers = pkg_info.get('CoMaintainers') or []
            if name and last_modified:
                is_co_maintainer = False
                all_maintainers = [maintainer] + comaintainers
                for maint in all_maintainers:
                    if not maint:
                        continue
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

def get_check_run_info(run_id: str) -> dict:
    """解析 check-update run 日志，提取 aur_missing 和 nvchecker_failed 的包集合"""
    try:
        log_output = run_gh_command(['run', 'view', str(run_id), '--log'])
        lines = log_output.split('\n')
        
        aur_missing_packages = set()
        nvchecker_failed_packages = set()
        in_process_updates = False
        
        for line in lines:
            # 检测 Process updates 步骤
            if 'Process updates' in line and 'python process-update.py' in line:
                in_process_updates = True
                continue
            elif in_process_updates and line.startswith('update	'):
                # 解析 "doesn't exist on AUR"
                if "doesn't exist on AUR" in line:
                    # 格式: "update	Process updates	HH:MM:SS.mmsZ python-librosa doesn't exist on AUR."
                    parts = line.split()
                    # 查找包名（通常在 "doesn't exist" 之前）
                    for i, part in enumerate(parts):
                        if "doesn't" in part or "exist" in part:
                            if i > 0:
                                pkg = parts[i-1]
                                aur_missing_packages.add(pkg)
                            break
                # 解析 "Failed to check update for <pkg>: event=..."
                elif "Failed to check update for" in line:
                    # 格式: "update	Process updates	HH:MM:SS.mmsZ Failed to check update for twitch-dl: event=running cmd."
                    # 提取包名
                    import re
                    match = re.search(r'Failed to check update for (\S+):', line)
                    if match:
                        pkg = match.group(1)
                        # 排除 event=running cmd 的情况（已被 process-update 忽略）
                        if "event=running cmd" not in line:
                            nvchecker_failed_packages.add(pkg)
                # 检测是否离开 Process updates 步骤
                elif line.startswith('update	Post Run'):
                    in_process_updates = False
        
        return {
            'aur_missing': aur_missing_packages,
            'nvchecker_failed': nvchecker_failed_packages
        }
    except Exception as e:
        print(f"   Error getting check run info for {run_id}: {e}")
        return {'aur_missing': set(), 'nvchecker_failed': set()}

def get_run_info(run_id: str) -> dict:
    """一次 log 调用，同时解析 build error、push conclusion"""
    try:
        log_output = run_gh_command(['run', 'view', str(run_id), '--log'])
        lines = log_output.split('\n')

        build_error = "No==>ERRORerrors"
        push_conclusion = ''
        in_push_job = False
        push_job_seen = False
        dep_error_lines = []  # 收集包含依赖错误的行
        dep_specific_lines = []  # 更具体的依赖错误（ pacman 的）

        for line in lines:
            # Build error detection
            if build_error == "No==>ERRORerrors":
                if '==> ERROR:' in line:
                    error_text = line.split('==> ERROR:')[1].strip()
                    if error_text:
                        build_error = error_text
                elif 'is greater than newver' in line:
                    error_text = line.strip()
                    if error_text:
                        build_error = error_text

            # Collect dependency-related errors (only from ==> ERROR: lines)
            if '==> ERROR:' in line:
                error_text = line.split('==> ERROR:')[1].strip()
                if any(keyword in error_text.lower() for keyword in [
                    'failed to install missing dependencies',
                    'could not resolve all dependencies',
                ]):
                    dep_specific_lines.append(error_text)
                    dep_error_lines.append(error_text)  # also add to general

            # Push job detection & conclusion
            if line.startswith('push\t'):
                in_push_job = True
                push_job_seen = True
            elif line.startswith('build\t'):
                in_push_job = False
            elif line.startswith('##[error]') and in_push_job:
                push_conclusion = 'failure'

        # 优先使用更具体的 pacman 依赖错误
        if dep_specific_lines:
            build_error = dep_specific_lines[0]
        elif dep_error_lines:
            build_error = dep_error_lines[0]

        # 如果 push job 存在且未发现 error，视为 success
        if push_job_seen and not push_conclusion:
            push_conclusion = 'success'

        return {'build_error': build_error, 'push_conclusion': push_conclusion}
    except Exception as e:
        print(f"   Error getting run info for {run_id}: {e}")
        return {'build_error': f"Failed: {e}", 'push_conclusion': ''}

def get_manual_fix_commits_since(check_time: datetime) -> set:
    """检查 check_time 之后的提交，找出修改了 config/ 目录下文件的提交，从中提取包名"""
    print("🔍 Checking for fixed packages by post-check commits...")
    try:
        # 使用 git log 查找 check_time 之后的提交，格式：<hash>|<author>|<date>|<subject>
        # 注意：git log --since 使用 ISO 8601 UTC 时间（以 Z 结尾），确保跨时区一致性
        since_time_utc = check_time.strftime('%Y-%m-%dT%H:%M:%SZ')
        result = subprocess.run(
            ['git', 'log', f'--since={since_time_utc}', '--format=%H|%an|%ai|%s', '--name-only'],
            cwd='/home/petron/auto_update_bot/aur-auto-update',
            capture_output=True, text=True, check=False
        )
        lines = result.stdout.split('\n')
        fixed_packages = set()
        current_commit_files = []
        in_files_section = False

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            # 使用 | 分隔符判断是否为 commit 头
            if '|' in line:
                # 处理上一个提交的文件列表
                if current_commit_files:
                    fixed_packages.update(extract_packages_from_paths(current_commit_files))
                    current_commit_files = []
                # 解析新 commit 头：格式 <hash>|<author>|<date>|<subject>
                parts = line.split('|', 3)
                if len(parts) >= 4:
                    commit_hash, author, date, subject = parts
                    if is_github_action_author(author):
                        in_files_section = False  # 跳过此提交的文件
                        continue
                in_files_section = True
            elif in_files_section and line_stripped:
                # 这是文件路径（不包含 |）
                current_commit_files.append(line_stripped)

        # 处理最后一个提交
        if current_commit_files:
            fixed_packages.update(extract_packages_from_paths(current_commit_files))

        print(f"   Found {len(fixed_packages)} fixed packages: {sorted(fixed_packages)}")
        return fixed_packages
    except Exception as e:
        print(f"   Error checking commits: {e}")
        return set()

def is_github_action_author(author: str) -> bool:
    """判断是否为 GitHub Actions 提交"""
    return author == "GitHub Actions" or 'github-actions[bot]' in author

def extract_packages_from_paths(paths: List[str]) -> set:
    """从文件路径列表中提取包名（config/<maintainer>/<pkg>.yaml）"""
    packages = set()
    for path in paths:
        # 只处理 config/ 目录下的 yaml 文件
        if not (path.startswith('config/') and path.endswith('.yaml')):
            continue
        parts = path.split('/')
        if len(parts) >= 3:
            pkg_file = parts[-1]  # <pkg>.yaml
            pkg_name = pkg_file[:-5] if pkg_file.endswith('.yaml') else pkg_file
            packages.add(pkg_name)
    return packages

def process_builds(build_runs: List[Dict], aur_info: Dict[str, tuple], check_time: datetime, check_run_id: str):
    # Get manual fix commits since check time
    fixed_packages = get_manual_fix_commits_since(check_time)
    
    # 从 check-update run 中获取每个包的额外状态（aur_missing, nvchecker_failed）
    print("🔍 Analyzing check-update run for aur_missing and nvchecker_failed states...")
    check_run_info = get_check_run_info(check_run_id)
    aur_missing_packages = check_run_info.get('aur_missing', set())
    nvchecker_failed_packages = check_run_info.get('nvchecker_failed', set())
    print(f"   Found {len(aur_missing_packages)} packages missing on AUR")
    print(f"   Found {len(nvchecker_failed_packages)} packages with nvchecker failures")

    # Calculate dynamic column widths (no AURUpdate column)
    all_packages = [build['package'] for build in build_runs]
    max_pkg_len = max(len(pkg) for pkg in all_packages) if all_packages else 0
    pkg_width = min(max_pkg_len + 2, 40)  # +2 padding, max 40
    run_id_width = 12
    status_width = 20
    total_width = pkg_width + run_id_width + status_width + 2  # 2 spaces between columns

    print("\n" + "="*total_width)
    print("📊 AUR Auto-Update Build Results")
    print("="*total_width)
    header = f"{'Package':<{pkg_width}} {'Run ID':<{run_id_width}} {'Status':<{status_width}}"
    print(header)
    print("-"*total_width)

    total = len(build_runs)
    # Status counts in FINAL ORDER: 📦 ✅ 🟢 ⚫ 🔴 🟡 ❌ 🚫 ⬜ ⚠️
    fully_successful_count = 0  # 📦
    fixed_count = 0             # ✅
    aur_updated_count = 0       # 🟢
    not_maintained_count = 0    # ⚫
    dependency_issue_count = 0  # 🔴
    vercmp_failed_count = 0     # 🟡
    build_failed_count = 0      # ❌
    push_failed_count = 0       # 🚫
    aur_missing_count = 0       # ⬜
    nvchecker_failed_count = 0  # ⚠️

    for build in build_runs:
        pkg = build['package']
        run_id = build['run_id']
        aur_data = aur_info.get(pkg)
        if aur_data:
            aur_time, is_co_maintainer = aur_data
            aur_success = aur_time > check_time if aur_time else False
        else:
            aur_time = None
            is_co_maintainer = False
            aur_success = False

        # 获取 run 信息（build error 和 push conclusion），自动缓存
        run_info = get_run_info(run_id)
        build_error = run_info['build_error']
        push_conclusion = run_info['push_conclusion']
        build_failed = build_error != "No==>ERRORerrors"
        vercmp_failed = "is greater than newver" in build_error.lower()

        # Priority order: 📦 ✅ 🟢 ⚫ 🟡 🔴 ❌ 🚫 ⬜ ⚠️

        # 1. Fixed
        if pkg in fixed_packages:
            status = "✅ Fixed"
            fixed_count += 1
        # 2. Non-co-maintainer
        elif not is_co_maintainer:
            status = "⚫ No longer maintained"
            not_maintained_count += 1
        # 3. AUR missing (check-update 环节发现包不在 AUR)
        elif pkg in aur_missing_packages:
            status = "⬜ AUR missing"
            aur_missing_count += 1
        # 4. nvchecker failed (check-update 环节检查失败)
        elif pkg in nvchecker_failed_packages:
            status = "⚠️ nvchecker failed"
            nvchecker_failed_count += 1
        # 5. Co-maintainer: evaluate build results
        else:
            # 5a. vercmp failed
            if vercmp_failed:
                status = "🟡 vercmp failed"
                vercmp_failed_count += 1
            # 5b. Dependency issue
            elif build_failed and any(keyword in build_error.lower() for keyword in [
                'failed to install missing dependencies',
                'could not resolve all dependencies',
            ]):
                status = "🔴 Dependency issue"
                dependency_issue_count += 1
            # 5c. Build failed but AUR updated -> 🟢
            elif build_failed and aur_success:
                status = "🟢 AUR updated"
                aur_updated_count += 1
            # 5d. Build failed -> ❌
            elif build_failed:
                status = "❌ Build failed"
                build_failed_count += 1
            # 5e. Push failed -> 🚫
            elif push_conclusion and push_conclusion != 'success':
                status = "🚫 Push failed"
                push_failed_count += 1
            # 5f. Build succeeded, push succeeded -> Success
            else:
                status = "📦 Success"
                fully_successful_count += 1

        display_name = pkg if len(pkg) <= pkg_width - 3 else pkg[:pkg_width - 6] + "..."
        print(f"{display_name:<{pkg_width}} {run_id:<{run_id_width}} {status:<{status_width}}")

    print("="*total_width)
    # Build summary string with only non-zero counts in priority order
    status_parts = []
    if fully_successful_count > 0:
        status_parts.append(f"📦{fully_successful_count}")
    if fixed_count > 0:
        status_parts.append(f"✅{fixed_count}")
    if aur_updated_count > 0:
        status_parts.append(f"🟢{aur_updated_count}")
    if not_maintained_count > 0:
        status_parts.append(f"⚫{not_maintained_count}")
    if vercmp_failed_count > 0:
        status_parts.append(f"🟡{vercmp_failed_count}")
    if dependency_issue_count > 0:
        status_parts.append(f"🔴{dependency_issue_count}")
    if build_failed_count > 0:
        status_parts.append(f"❌{build_failed_count}")
    if push_failed_count > 0:
        status_parts.append(f"🚫{push_failed_count}")
    summary = " ".join(status_parts)
    print(f"Total: {total} packages ({summary})")

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
        process_builds(build_data, aur_info, check_time, check_run_id)
    except Exception as e:
        print(f"\n❌ Script execution failed: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == '__main__':
    main()
