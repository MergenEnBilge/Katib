# Drawing and shortcuts

## The shapes

| Kind | Tool | How |
|------|------|-----|
| Boxes | **B** | Drag a rectangle. |
| Polygons | **P** | Click around an outline, then press Enter or click the first point to close it. |
| Rotated boxes | **O** | Drag along one edge, then move out to the other side and click. Drag the round handle to turn the box. |
| Keypoints | **K** | Click each landmark in order. Shift+click marks one as hidden, **N** skips one, Enter finishes early. |
| Brush masks | **R** | Paint. **E** switches to the eraser. **[** and **]** change the brush size. |
| Magic wand | **W** | Click inside an object to outline the area of similar color. **[** and **]** change how alike the colors must be. |
| Click to select | **S** | Click an object and a model outlines it. Shift+click adds what it missed, Ctrl+click cuts back what it took too much of. Only appears when a model is loaded — see [Model help](assist.md). |
| Image tags | | Switch a class on under "Tags on this image". |
| Text | | Open the **Text** tab and write. See below. |

The toolbar shows only the tools your project can save. To change which kinds a project uses, ask an owner to create a new project with the kinds you need.

### Keypoints need landmarks

Open **Manage classes**, choose a class, and write its landmarks one per line, for example `nose`, `left eye`, `right eye`. To draw lines between landmarks, list pairs of numbers such as `1-2, 1-3`. Landmarks are placed in this order with the keypoints tool.

While a shape is selected, hover a landmark and press **V** to mark it hidden, or **Delete** to mark it as not labeled.

## Writing text

Choose **Text** when you create a project to label pictures with words. Two things become possible:

- **Captions.** Open the **Text** tab on the right and choose **Add text**. Write a caption, a description or any note about the whole picture. Add as many entries as you need. Each one can carry an optional label, such as `caption` or `question`, chosen from your classes. Text saves as you leave the box, like everything else.
- **Words inside a shape.** With the Text kind on, selecting a box, polygon or rotated box shows a **Text in this shape** field in the Details tab. Use it to write down the word on a sign or a line from a document. The words appear next to the class name on the picture.

Export both with **Tags and text (JSON Lines)**. See [Images, folders and formats](data.md#tags-and-text).

## Selecting and editing

- Click a shape to select it, or drag on empty space to select several.
- Drag a shape to move it. Drag a handle to resize it.
- **Tab** and **Shift+Tab** step through the shapes on the image.
- Arrow keys nudge the selection by one pixel. Hold Shift for ten.
- **Ctrl+D** duplicates. **Ctrl+C** and **Ctrl+V** copy and paste between images.
- **Delete** removes the selection. **Ctrl+Z** and **Ctrl+Shift+Z** undo and redo. Undo history lasts for the image you have open.
- Press a number key (**1** to **9**) to change the class of the selected shapes, or to choose the class you will draw with.

Locked classes cannot be edited, and hidden classes cannot be selected. Use the eye and lock buttons next to each class.

## Moving around

| Action | How |
|--------|-----|
| Zoom | **+**, **-**, or Ctrl and the scroll wheel |
| Fit to view | **0** |
| Pan | Hold **Space** and drag, or scroll. On a touch screen, drag with two fingers |
| Hide all shapes | **H** |
| Next and previous image | **D** and **A**, or the arrow keys |
| Mark as done and continue | **Shift+Enter** |
| Fold the image list away | **[** |
| Fold the classes and details panel away | **]** |
| Give the picture the whole window | **\** |

Folding is remembered, so the workspace looks the way you left it next time. On the home screen, **[**
folds the sidebar down to its icons.

## On a phone or tablet

The interface adapts to the screen. Handles get larger touch targets, and two fingers pan and zoom. Open Katib from the address in **Share** (see [Working together](teams.md#sharing-on-your-network)), and install it from your browser's menu to keep it on your home screen.

If the signal drops while you draw, your edits are kept on the device and sent when you open Katib again with a connection. Images you have not opened yet are not available offline.

## All shortcuts

Press **?** inside Katib for the full list, which is always up to date.
