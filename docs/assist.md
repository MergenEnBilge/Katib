# Model help

Katib has three ways to draw less by hand. None of them sends anything off your computer.

## Magic wand

Press **W**, click inside an object, and Katib outlines the area around the click that has a similar color, as a polygon. Move the pointer first to see a preview.

Press **]** to accept a wider range of colors, or **[** for a narrower one. It works best on objects that stand out from their background. It needs no model and no setup.

## Click to select

Where the magic wand follows colour, this follows shapes. Click a dog on a lawn and you get the
dog, not the patch of brown fur the wand would have found. It needs a Segment Anything model, which
you supply.

Press **S**, then click the middle of an object. The first click on a picture takes a second or
two while the model reads it; every click after that on the same picture is quick. If the outline
grabbed too little, shift-click the part it missed. If it grabbed too much, ctrl-click the part it
should let go of. Escape starts over.

### Setting it up

Segment Anything comes in two files: an **image encoder**, which reads the picture, and a **mask
decoder**, which turns your click into an outline. Both have to be ONNX exports of the same model.

1. Install the extra package: `uv sync --extra ml`. The Docker image already has it.
2. Turn model help on under **Settings**, then **Model help**.
3. Still under Model help, choose a file for each half. Katib stores them on the server, so you do
   this once and everyone on that Katib can click to select.

**Which model.** MobileSAM is the one to start with: its encoder is about 25 MB and it is quick
enough on an ordinary laptop. The original SAM models work too and are better at awkward edges,
but the largest of them will keep you waiting several seconds per picture without a graphics card.
Get the ONNX exports from the model's own project — Katib never downloads anything.

**Where the work happens.** On the server, not in your browser. A phone or an old laptop gets the
same results as the machine Katib runs on, and no picture leaves it.

The tool appears in the toolbar only in projects that use polygons, and only once both halves are
loaded. Uploading either half again replaces it.

## Pre-label with your own model

If you already have a YOLO detection model saved as ONNX, Katib can draft boxes for you to correct.

1. Install the extra package: `uv sync --extra ml`. The Docker image already has it.
2. Turn it on under **Settings**, then **Model help**. It takes effect at once, with no restart.
3. In a project, choose **Pre-label with a model** (the sparkle button) and press **Add a model**.
   Pick your `.onnx` file. It is stored on the server, so you do this once and everyone using that
   Katib can pre-label with it.
4. Choose the model and a minimum confidence, then run it.

You can also copy `.onnx` files straight into the `models` folder inside Katib's data folder, which
the window shows the path to. That is often quicker when Katib runs on your own machine. With
Docker the folder is inside the container, so uploading is the way in.

To keep models somewhere else, set `ml.models_dir`. Uploads are capped by `limits.max_model_mb`,
which is 500 MB.

Only people who can manage the project can run a model. Model boxes need a project that uses boxes.

### What models work

Katib runs detection models exported from YOLO tools in the YOLOv8 layout (candidates in columns) or the YOLOv5 layout (candidates in rows). The picture is fitted to the model's input size with gray padding, and boxes are mapped back onto your original image. Models that already include their own non-maximum suppression, or that detect something other than boxes, are not supported.

Models exported from common tools list their class names, and Katib reads them. If yours does not, the window asks you to type the names in, one per class, in the model's order.

### What you get

Boxes are saved like any other box, marked as coming from a model with the model's confidence. They are drawn dashed, and the class gallery can filter for them. Correct them like any box. Every run is written to the history and can be undone as a whole for 30 days. Boxes you have edited since are left alone.

You choose whether to draft boxes only for images without shapes (the default) or for all images. Existing shapes are never changed.

### Missing classes

By default, Katib creates a class for anything the model finds that the project does not have yet. Turn this off to leave those detections out. Katib matches by class name, ignoring case, and by earlier names of a renamed class.

### Not included

Pre-labeling runs detection models only, and draws boxes. A segmentation model belongs under
**Click to select** above, which is where its two halves go. Tracking across video frames is not
something Katib does.
