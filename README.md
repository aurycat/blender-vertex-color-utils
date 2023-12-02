# Vertex Color Utils add-on for Blender

Tested with Blender 3.6.5 and 4.0.1

## Installation

1. [Download the plugin zip](https://gitlab.com/aurycat/blender-vertex-color-utils/-/archive/main/blender-vertex-color-utils-main.zip).
2. In Blender, go to Edit > Preferences > Add-ons and click "Install...". Select the downloaded **zip file**.
3. In the add-ons list, click the checkbox on "Mesh: Vertex Color Utils" to enable it.

## Features

### Color Channel Masking (`Vertex Paint > Paint > Mask R/G/B/A`)

   Edit a subset of color channels at once. There are only menu buttons for creating a single-channel mask, but the operator options popup lets you select multiple of R, G, or B simultaneously to create a mask for.

   Once you are sastisfied with the mask edit, use `Vertex Paint > Paint > Apply Channel` Mask to apply the mask edit.

   Masks are created as additional color attribute layers with a suffix such as `__R`, `__GB`, etc. You can switch back to the base attribute layer while a mask is active, but only one mask for a particular channel can exist simultaneously (to prevent "merge conflict"-style issues).

   When editing a red mask, only paint with red; other colors are ignored. Likewise with green and blue masks. When creating an alpha channel mask, the plugin uses grayscale colors to represent the alpha channel, but when applying that alpha mask, only the mask's red channel is actually considered.


### Color Channel Swizzling (`Vertex Paint > Paint > Swizzle / Reorder Channels`)

   Swap color channels, e.g. swap the Red and Green channels, or copy the Red channel into the Alpha channel.

   A swizzle string is a series of 4 characters out of R, G, B, A, 0, and 1 (lowercase letters are okay too).

   Examples:\
   `RGBA`: This is the "no-op" swizzle string; it puts every channel into the location it's already at, so nothng changes.\
   `BGRA`: Changes RGB to BGR.\
   `000R`: Moves the red channel into alpha channel, and then zeros out the other channels.\
   `1G11`: Sets all channels to 1, except green.


### Sample Vertex Color (`Vertex Paint > Paint > Sample Vertex Color`)

   Find out the color value of a particular vertex (supporting face-corner aka vertex-per-face colors). This tool opens a modal color picker.

   Hover your mouse over a face on the mesh, and the closest vertex of that face to the mouse is the targeted vertex. The color of that vertex will be shown on the header bar automatically.

   Ctrl-leftclick to write out the color (same as what's shown in the header bar) to the info log (`Editor Type > Info`) for easy copying.

   Leftclick to set the color of the current painting brush to the vertex color and exit sampling mode.

   Press ESC or rightclick to exit sampling mode.

   Note on Linear vs sRGB: For primary colors (all channels are 00 or FF), linear and sRGB are the same, so the plugin only shows one color. Otherwise, the plugin shows both the linear and sRGB color values. The sRGB value is what Blender uses for the brush colors. When importing or exporting a mesh, it is the importer/exporter that decides whether vertex colors are considered to be linear or sRGB. For example, in the FBX export menu, go to `Geometry > Vertex Colors` to select whether to export the sRGB or Linear values.


### Gamma correction (`Vertex Paint > Paint > Linear to sRGB / sRGB to Linear`)

   These might be useful in some situations. Hover your mouse over the options in the menu to read the tooltip text for more information about both of these operators. Also see "Note on Linear vs sRGB" in Sample Vertex Color section above.


## Etc

Created by aurycat. MIT license.