#!/usr/bin/env python3
"""Carry the pinned Go modules' and toolchain's license notices into archives."""
import json
import os
import pathlib
import subprocess
import sys


def notices():
    decoder = json.JSONDecoder()
    sections = ['Third-party notices for the Woobe CLI distribution.\n'
                'These notices do not grant a license to the Woobe CLI itself.']
    modules = {}
    for system in ['linux', 'darwin', 'windows']:
        for arch in ['amd64', 'arm64']:
            env = dict(os.environ, GOOS=system, GOARCH=arch, CGO_ENABLED='0')
            result = subprocess.run(['go', 'list', '-deps', '-json', './cmd/woobe'], env=env,
                                    check=True, capture_output=True, text=True).stdout
            while result.strip():
                package, length = decoder.raw_decode(result.lstrip())
                result = result.lstrip()[length:]
                module = package.get('Module')
                if module and not module.get('Main'):
                    modules[module['Path']] = module
    for module in sorted(modules.values(), key=lambda value: value['Path']):
        root = pathlib.Path(module['Dir'])
        licenses = [root / name for name in ['LICENSE', 'LICENSE.txt', 'LICENSE.md'] if (root / name).is_file()]
        if not licenses:
            raise ValueError(f"missing dependency license: {module['Path']}")
        label = f"{module['Path']} {module['Version']}"
        sections.append(label + '\n' + licenses[0].read_text())
        notice = root / 'NOTICE'
        if notice.is_file():
            sections.append(label + ' NOTICE\n' + notice.read_text())
    go_root = pathlib.Path(subprocess.run(['go', 'env', 'GOROOT'], check=True,
                                         capture_output=True, text=True).stdout.strip())
    sections.append('Go runtime and standard library\n' + (go_root / 'LICENSE').read_text())
    for license_file in sorted((go_root / 'src/vendor').rglob('LICENSE')):
        sections.append(str(license_file.relative_to(go_root)) + '\n' + license_file.read_text())
    return ('\n\n' + '=' * 72 + '\n\n').join(sections) + '\n'


if __name__ == '__main__':
    pathlib.Path(sys.argv[1]).write_text(notices())
