# Auto update bot [![AUR auto update](https://github.com/arch4edu/aur-auto-update/actions/workflows/update.yml/badge.svg)](https://github.com/arch4edu/aur-auto-update/actions/workflows/update.yml)
Automatically update the PKGBUILD on AUR when there is a new version of a package.

## Quick guide

* Add `AutoUpdateBot` as a co-maintainer of your package on AUR.
* Add the corresponding [nvchecker](https://github.com/lilydjwg/nvchecker) configuration in [`nvchecker.toml`](https://github.com/arch4edu/aur-auto-update/blob/main/nvchecker.toml). You can locally test your newly added configuration with:
  ```sh
  nvchecker -c nvchecker.toml -e the_added_package
  ```
* (Optional) Write the corresponding `update/${pkgbase}.sh` for your package if necessary.
  * The default script `update/default.sh` will automatically strip the leading non-version characters, and is suitable for versions like `1.0.0`, `v1.0.0`, `version-1.0.0`.
* Create a pull request to submit your changes and pass the checks.
  * Remember to take a look at the check results.
* Done. You can check the outputs of [GitHub Actions](https://github.com/arch4edu/aur-auto-update/actions) if there is anything wrong.
  * It runs every day.
