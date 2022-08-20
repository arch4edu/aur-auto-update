import toml
import subprocess
import requests
import re
import json

maintainer_line_re = re.compile(r'Maintainer:</th>[^<]*<td>([^<]*)</td>')
maintainer_re = re.compile(r"[a-zA-z_]+")

def check_sorted(config):
    keys = [i for i in config.keys()]
    if keys == sorted(keys):
        print('The entries in nvchecker.toml is sorted.')
    else:
        raise Exception('The entries in nvchecker.toml is not well sorted.')

def check_aur_maintainer(package):
    content = requests.get(f'https://aur.archlinux.org/pkgbase/{package}').content.decode('utf-8')
    maintainers = maintainer_line_re.search(content.replace('\n', '')).group(1)
    maintainers = maintainer_re.findall(maintainers)
    if 'AutoUpdateBot' in maintainers:
        print(f'AutoUpdateBot is a maintainer or co-maintainer of {package}.')
    else:
        raise Exception(f'AutoUpdateBot is not a maintainer or co-maintainer of {package}.')

def check_nvchecker(new_config):
    config = {}
    config['__config__'] = {}
    config['__config__']['oldver'] = '/dev/null'
    config['__config__']['keyfile'] = 'keyfile.toml'

    for package, package_config in new_config:
        config[package] = package_config

    with open('check.toml', 'w') as f:
        toml.dump(config, f)

    output = subprocess.run(['nvchecker', '--logger', 'json', '-c', 'check.toml'], capture_output=True)
    output = output.stdout.decode('utf-8').split('\n')[:-1]
    for line in output:
        result = json.loads(line)
        if result['event'] in ['error', 'unexpected error happened']:
            print(line)
            raise Exception(f'Failed to find the version for {result["name"]}.')
        else:
            print(f'Successfully find version {result["version"]} for {result["name"]}.')

if __name__ == '__main__':

    subprocess.run(['git', 'checkout', '-q', 'main'])
    with open('nvchecker.toml') as f:
        old_config = toml.load(f)

    subprocess.run(['git', 'checkout', '-q', '-'])
    with open('nvchecker.toml') as f:
        new_config = toml.load(f)

    check_sorted(new_config)

    new_config = [(i, new_config[i]) for i in new_config.keys() if not i in old_config]

    for package, _ in new_config:
        check_aur_maintainer(package)

    check_nvchecker(new_config)
