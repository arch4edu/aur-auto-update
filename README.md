# Auto update bot [![AUR auto update](https://github.com/arch4edu/aur-auto-update/actions/workflows/check-update.yml/badge.svg)](https://github.com/arch4edu/aur-auto-update/actions/workflows/check-update.yml) [![DeepWiki](https://deepwiki.com/badge-maker?url=https%3A%2F%2Fdeepwiki.com%2Farch4edu%2Faur-auto-update)](https://deepwiki.com/arch4edu/aur-auto-update)
Automatically update the PKGBUILD on AUR when there is a new version of a package.

## Warning

* We have implemented the test mechanism but the documents haven't been updated yet.

## Quick guide

* Add `AutoUpdateBot` as a co-maintainer of your package on AUR.
* Add the corresponding [nvchecker](https://github.com/lilydjwg/nvchecker) configuration under `config`. You can locally test your newly added configuration with:
  ```sh
  python nvchecker.py config/path/to/the_added_package.yaml
  nvchecker -c nvchecker.toml -e the_added_package
  ```
* (Optional) Write a custom update script to `config/path/to/the_added_package.override` to override `bin/update-pkgver` if necessary.
* Create a pull request to submit your changes and pass the checks.
  * Remember to take a look at the check results.
* Done. You can check the outputs of [GitHub Actions](https://github.com/arch4edu/aur-auto-update/actions) if there is anything wrong.
  * It runs every day.
