# cc2_anm_export_blender
Animation exporter for CyberConnect2 games (Ultimate Ninja Storm / All Star Battle series).

Uses [xfbin-rs-py](https://github.com/maxcabd/xfbin-rs-py) for writing XFBIN files.

## Requirements
Requires the XFBIN Blender addon for versions `3.65` and below, get it [here](https://github.com/maxcabd/cc2_xfbin_blender_anm/releases)

## Installing
Download the [latest release](https://github.com/maxcabd/cc2_anm_export_blender/releases/latest) and install it in Blender. To do so, follow the instructions in the [official Blender manual](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html) for installing add-ons, or follow the brief instructions below.

Open the `Edit` -> `Preferences` window from the menu bar, go to `Add-ons`, click on the `Install` button, and select the release zip you downloaded. Then, enable the script by checking the box next to it.

## Future Updates
- Optimizations
- Option to inject animations
- Support for material animations
- Support for light animations

## Credits
- Thanks to [TheLeonX](https://www.youtube.com/c/TheLeonx) for supporting the project with importing / exporting correct bone transformations, material animations, and more.
- A big thanks to [SutandoTsukai181](https://github.com/mosamadeeb) for his initial work on the animation importer and for reversing the animation tracks from the .xfbin files.
- And HallucinatingGenius for his donations ❤️
