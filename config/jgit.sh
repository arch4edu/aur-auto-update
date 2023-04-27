#!/bin/sh
newver="${2//-/_}"
force="$2"

if [ -z "${force}"]
then
	oldver=$(grep -P '^pkgver' PKGBUILD | cut -d= -f2)
	[ "${oldver}" = "${newver}" ] && echo "${pkgbase} is already at ${newver}" && exit 0
	[ $(vercmp "${oldver}" "${newver}") -eq 1 ] && echo "The oldver ${oldver} is greater than newver ${newver}." && exit 1
fi

sed "s/^pkgver=.*$/pkgver=${newver}/" -i PKGBUILD
sed "s/^pkgrel=.*$/pkgrel=1/" -i PKGBUILD

su makepkg -c 'updpkgsums'
