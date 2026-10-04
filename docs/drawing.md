# Drawing and shortcuts

This guide explains each tool in the workspace and the keys that control it. Press **?** inside
Katib at any time to see the full list.

## The tools

| Shape | Key | How to use it |
|-------|-----|---------------|
| Box | **B** | Drag a rectangle around the object. |
| Polygon | **P** | Click around the outline. Press Enter, or click the first point, to close the shape. |
| Rotated box | **O** | Drag along one edge, move to the other side, then click. Drag the round handle to turn the box. |
| Keypoints | **K** | Click each point in order. Shift+click marks a point as hidden. **N** skips a point. Enter finishes early. |
| Brush mask | **R** | Paint over the area. **E** switches to the eraser. **[** and **]** change the brush size. |
| Magic wand | **W** | Click inside an object to outline the area with similar colours. **[** and **]** change how alike the colours must be. |
| Click to select | **S** | Click an object and a model outlines it. Shift+click adds a missed part. Ctrl+click removes an extra part. This only appears when a model is loaded. See [Model help](assist.md). |
| Image tags | | Turn on a class under **Tags on this image**. |
| Text | | Open the **Text** tab and write. See [Writing text](#writing-text). |

The toolbar only shows the tools your project can use. To change which shapes a project uses, create a
new project with the shapes you need.

### Keypoints need named points

Open **Manage classes**, choose a class, and type its points, one per line. For example: `nose`,
`left eye`, `right eye`. To draw lines between points, list the pairs of point numbers, such as
`1-2, 1-3`. The keypoint tool places the points in this order.

While a keypoint shape is selected, hover over a point and press **V** to mark it hidden. Press
**Delete** to mark it as not labelled.

## Writing text

Choose **Text** when you create a project if you want to write words on your pictures. There are two
ways to use it.

- **Captions.** Open the **Text** tab on the right, then choose **Add text**. Write a caption, a
  description or a note about the whole picture. You can add as many as you need. Each one can have a
  label, such as `caption` or `question`, picked from your classes. Text saves when you leave the box.
- **Words inside a shape.** When the Text shape is on, select a box, polygon or rotated box. The
  **Details** tab shows a **Text in this shape** field. Use it for the words on a sign or a line of a
  document. The words appear next to the class name on the picture.

To export captions and text, choose **Tags and text (JSON Lines)**. See
[Pictures, folders and formats](data.md#tags-captions-and-text).

## Selecting and editing

- Click a shape to select it. Drag on empty space to select several at once.
- Drag a shape to move it. Drag a handle to resize it.
- **Tab** and **Shift+Tab** move from one shape to the next.
- Arrow keys move the selection one pixel. Hold **Shift** to move it ten pixels.
- **Ctrl+D** makes a copy of the selection. **Ctrl+C** and **Ctrl+V** copy and paste between pictures.
- **Delete** removes the selection.
- **Ctrl+Z** undoes and **Ctrl+Shift+Z** redoes. Undo works on the picture you have open.
- Press a number key, **1** to **9**, to change the class of the selected shapes. With nothing
  selected, the number chooses the class you draw with next.

Locked classes cannot be edited, and hidden classes cannot be selected. Use the eye and lock buttons
next to each class to change this.

## Moving around the picture

| To do this | Press |
|------------|-------|
| Zoom in or out | **+** or **-**, or Ctrl and the scroll wheel |
| Fit the picture to the window | **0** |
| Move the picture | Hold **Space** and drag, or scroll. On a touch screen, drag with two fingers |
| Hide all shapes | **H** |
| Go to the next or previous picture | **D** and **A**, or the arrow keys |
| Mark the picture as done and go on | **Shift+Enter** |
| Hide the picture list | **[** |
| Hide the classes and details panel | **]** |
| Give the picture the whole window | **\\** |

Katib remembers which panels you hid, so the workspace looks the same the next time you open it. On
the home screen, **[** shrinks the sidebar to icons.

## Text documents

In a project that uses **Text spans**, Katib shows the words of a document instead of a canvas.

1. Choose a class on the right.
2. Select the words you want to label, with the mouse or by holding on a touch screen.
3. The span appears as soon as you let go, in that class's colour.

Katib leaves out any space at the edges of what you selected, so a span never ends with a blank.

| To do this | How |
|------------|-----|
| Change a span's class | Click it, then press a number key or choose a class |
| Remove a span | Click it and press Delete, or use the bin button in the list |
| See every span | The list under the words. Each one shows its class and the words it covers |
| Undo | **Ctrl+Z**, the same as anywhere else |

Spans can overlap, which is what you want when a phrase and a word inside it both need a label.
Where they do, the words take the colour of the longer span, and both are listed underneath.

You can also tag a whole document from the Classes tab, which suits sorting documents into
categories, and write captions in the Text tab.

## On a phone or tablet

The layout adapts to the screen. Handles are bigger for touch, and two fingers can pan and zoom.
Open Katib from the address shown under **Share**, and add it to your home screen from your browser's
menu. See [Working together](teams.md#sharing-on-your-network).

If the connection drops while you are drawing, your changes are kept on the device. They are sent when
you reconnect. Pictures you have not opened yet are not available without a connection.
