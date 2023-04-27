#!/bin/sh
newver=$(echo "$1" | sed 's/^[^.0-9]*//')
force="$2"

[ $newver = version-* ] && exit 0

if [ -z "${force}"]
then
	oldver=$(grep -P '^_subver' PKGBUILD | cut -d= -f2)
	[ "${oldver}" = "${newver}" ] && echo "${pkgbase} is already at ${newver}" && exit 0
	[ $(vercmp "${oldver}" "${newver}") -eq 1 ] && echo "The oldver ${oldver} is greater than newver ${newver}." && exit 1
fi

_pkgver=$(grep -P '^_pkgver' PKGBUILD | cut -d= -f2)

sed "s/^_subver=.*$/_subver=${newver}/" -i PKGBUILD
sed "s/^pkgver=.*$/pkgver=${_pkgver}.${newver}/" -i PKGBUILD
sed "s/^pkgrel=.*$/pkgrel=1/" -i PKGBUILD

su makepkg -c 'updpkgsums'
