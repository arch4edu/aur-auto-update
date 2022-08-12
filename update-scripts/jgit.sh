#!/bin/sh
pkgbase="$1"
newver="${2//-/_}"

git clone ssh://aur@aur.archlinux.org/${pkgbase}.git
git config --global --add safe.directory $(realpath ${pkgbase})
chown makepkg:root -R ${pkgbase}

cd ${pkgbase}

oldver=$(grep -P '^pkgver' PKGBUILD | cut -d= -f2)
[ "${oldver}" = "${newver}" ] && echo "${pkgbase} is already at ${newver}" && exit 0

sed "s/^pkgver=.*$/pkgver=${newver}/" -i PKGBUILD
sed "s/^pkgrel=.*$/pkgrel=1/" -i PKGBUILD

su makepkg -c 'updpkgsums'
su makepkg -c 'makepkg --printsrcinfo' > .SRCINFO
git add PKGBUILD .SRCINFO
git commit -m "auto updated to ${newver}"
git push origin master
