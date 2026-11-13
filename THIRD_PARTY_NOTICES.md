# Third-party notices

VGI is an independent implementation distributed under the [MIT license](LICENSE). Its original implementation name was Universal Recompilation Diagnostics (URD). Referenced projects and optional dependencies retain their own licenses.

## Hookshot

- Repository: <https://github.com/NotRexed/Hookshot>
- Inspected source commit: [`e9975d6c245275aaf89a34e8d17a6bbe8badab46`](https://github.com/NotRexed/Hookshot/tree/e9975d6c245275aaf89a34e8d17a6bbe8badab46)
- Upstream licensing at that inspection point: README identifies **GPL-3.0-or-later**; the root LICENSE contains GPLv3 text. Upstream third-party components retain their own notices.

The native adapter independently parses observed export formats. No upstream implementation files are included in this distribution or copied into its adapter production code. Inspection of a schema does not verify a user's executable or establish compatibility with every upstream version. Immutable source paths and clock/schema evidence are documented in [docs/HOOKSHOT_INSTRUMENTATION.md](docs/HOOKSHOT_INSTRUMENTATION.md). Source links identify instrumentation emission, not defective-code attribution.

VGI is not affiliated with, sponsored by, or endorsed by Hookshot or its contributors. A temporary research checkout is not part of the distributed independent implementation.

## Python

VGI requires Python 3.10 or newer and uses its standard library. The Python runtime is separately licensed under the Python Software Foundation license and applicable notices: <https://docs.python.org/3/license.html>. The runtime is not bundled with this repository.

## Pillow — optional

Pillow enables local image analysis and is not bundled in this repository. The current upstream license identifies **MIT-CMU**, with applicable component notices. Earlier releases may use different terms; the license shipped with the installed version governs that dependency. Consult that version's notices and the [upstream license](https://github.com/python-pillow/Pillow/blob/main/LICENSE). Installing Pillow does not change the license of VGI's original code.

## Test data and excluded content

Synthetic fixture data and fixture images are generated for software tests and remain explicitly labeled synthetic. No game executable, ROM, proprietary asset, shader/program dump, save, real-game screenshot, or upstream implementation source is included as project test data. Do not add such material to public contributions.
