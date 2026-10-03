# Model help

Katib has three ways to save you time on drawing. The magic wand needs no setup. The other two use a
model that runs on your server. Nothing leaves your server while the tools run. The only time Katib
connects to the internet is when an administrator asks it to download a model by name.

## Magic wand

Press **W**, then click inside an object. Katib outlines the area around the click that has similar
colours, and draws it as a polygon. Move the pointer first to see a preview.

Press **]** to include a wider range of colours, or **[** for a narrower range. The wand works best on
objects that stand out from their background. It needs no model and no setup.

## Click to select

The magic wand follows colour. Click to select follows the shape of the object. Click a dog on a lawn,
and you get the dog, not the patch of brown grass the wand might pick up. This tool needs a Segment
Anything model. You can download one by name, or bring your own.

Press **S**, then click the middle of the object. The first click on a picture takes a second or two,
while the model reads the picture. Each click after that is quick.

- If the outline missed part of the object, **Shift+click** that part to add it.
- If the outline took in too much, **Ctrl+click** the extra part to remove it.
- Press **Escape** to start again.

If nothing confident is near the click, Katib says **Nothing found there**, rather than drawing a wrong
outline. A small model such as MobileSAM says this more often than a large one, especially on a busy
picture or near the edge of an object. Try clicking the middle of the object again, or use a larger
model. See **Setting it up** below.

### Setting it up

A Segment Anything model comes in two files:

- an **image encoder**, which reads the picture, and
- a **mask decoder**, which turns your click into an outline.

Both files must be ONNX exports of the same model.

1. Install the extra package with `uv sync --extra ml`. The Docker image already includes it.
2. Under **Settings**, then **Model help**, turn model help on.
3. In the same section, choose **Download** next to one of the models Katib knows about. You can also
   choose a file for each half if you already have them. Either way, the files are stored on your
   server, so you only set this up once. Everyone who uses that Katib can then use click to select.

**Which model to choose.** Start with MobileSAM. Its encoder is about 25 MB, and it runs quickly on an
ordinary laptop. ViT-B is more accurate on difficult edges, but it is about seven times larger. Without a
graphics card, each picture will take noticeably longer.

Katib checks each download against the exact file it expects, and refuses a file that does not match. If
you would rather Katib never connect to the internet, download the files yourself and choose them.

**Where the work happens.** On your server, not in your browser. A phone or an old laptop gets the same
results as the server, and no picture leaves it.

The tool only appears in projects that use polygons, and only once both halves are loaded. Uploading
either half again replaces the old one.

## Draft boxes with your own model

If you have a YOLO detection model saved as an ONNX file, Katib can draft boxes for you to correct.

1. Install the extra package with `uv sync --extra ml`. The Docker image already includes it.
2. Under **Settings**, then **Model help**, turn it on. It takes effect straight away, with no restart.
3. In a project, choose **Pre-label with a model** (the sparkle button), then **Add a model**. Choose your
   `.onnx` file. It is stored on the server, so you only add it once.
4. Choose the model and a minimum confidence, then run it.

If Katib runs on your own computer, you can also copy `.onnx` files straight into the `models` folder in
Katib's data folder. The window shows you where that folder is. With Docker, the folder is inside the
container, so upload the file from the browser instead.

To keep models somewhere else, set `ml.models_dir`. Uploads are limited to `limits.max_model_mb`, which
is 500 MB by default.

Only people who can manage the project can run a model. The model's boxes need a project that uses boxes.

### Which models work

Katib runs detection models exported from YOLO tools. It accepts both output layouts: YOLOv8 (candidates
in columns) and YOLOv5 (candidates in rows). The picture is padded with grey to fit the model's input
size, and the boxes are mapped back onto your original picture.

Katib does not support models that already include their own non-maximum suppression, or models that
detect something other than boxes.

Katib reads the class names stored in most models. If your model does not include them, Katib asks you
to type them in, one per class, in the order the model uses.

### What you get

Each box is saved like any other box, and marked as coming from a model, with the model's confidence. Boxes
from a model are drawn with a dashed outline, and the class gallery can filter them. Correct them as you
would any other box.

Each run is recorded in **History**, and you can undo the whole run for 30 days. Boxes you have edited since
the run are left alone.

You choose whether to draft boxes only for pictures without shapes, which is the default, or for every
picture. Existing shapes are never changed.

### Missing classes

By default, Katib creates a class for anything the model finds that the project does not have yet. Turn
this off if you want to leave those detections out. Katib matches classes by name, ignoring capital
letters, and it also matches earlier names of a renamed class.

### Not included

Draft boxes only work with detection models, and they only produce boxes. A segmentation model goes under
**Click to select**, where its two halves are loaded. Katib does not track objects across video frames.
