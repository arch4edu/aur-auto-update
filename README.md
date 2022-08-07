# Auto update bot [![AUR auto update](https://github.com/arch4edu/aur-auto-update/actions/workflows/update.yml/badge.svg)](https://github.com/arch4edu/aur-auto-update/actions/workflows/update.yml)
Automatically update the PKGBUILD on AUR when there is a new version of a package.

## Quick guide

* Add `AutoUpdateBot` as a co-maintainer of your package on AUR.
* Create a pull request to add the corresponding [nvchecker](https://github.com/lilydjwg/nvchecker) configuration in [`nvchecker.toml`](https://github.com/arch4edu/aur-auto-update/blob/main/nvchecker.toml).  
  There might be a more simple way for this step in the future instead of creating pull requests.
* (Optional) Write the corresponding `update/${pkgbase}.sh` for your package if necessary.  
  The default is `update/default.sh`
* Done. You can check the outputs of [GitHub Actions](https://github.com/arch4edu/aur-auto-update/actions) if there is anything wrong.  
  It runs every day.
